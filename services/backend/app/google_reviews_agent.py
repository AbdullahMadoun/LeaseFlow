"""Google Maps reviews agent: company name -> matched place -> review summary."""
from __future__ import annotations

import copy
import json
import logging
import math
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx

from .config import CONFIG
from .supabase_client import get_client
from .tracing import traced_llm_call, write_event

log = logging.getLogger(__name__)
_REPORT_CACHE_TTL = timedelta(hours=12)
_REPORT_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}
_GENERIC_NAME_TOKENS = {"restaurant", "cafe", "coffee", "shop", "co", "company", "ltd", "llc", "ksa", "the", "and"}
_SAUDI_REGION_ALIASES = {
    "eastern": "Eastern Region",
    "eastern province": "Eastern Region",
    "eastern region": "Eastern Region",
    "ash sharqiyah": "Eastern Region",
    "ash sharqiyah region": "Eastern Region",
    "al sharqiyah": "Eastern Region",
    "sharqiyah": "Eastern Region",
    "الشرقية": "Eastern Region",
    "المنطقة الشرقية": "Eastern Region",
}


class GoogleReviewsError(RuntimeError):
    """Base error for Google reviews agent failures."""


class GooglePlaceNotFound(GoogleReviewsError):
    """Raised when no strong Google Maps place match is found."""


class GooglePlaceAmbiguous(GoogleReviewsError):
    """Raised when multiple Google Maps places match the company name too closely."""

    def __init__(self, company_name: str, candidates: list[dict[str, Any]]) -> None:
        self.company_name = company_name
        self.candidates = candidates
        super().__init__(f"Ambiguous Google Maps match for {company_name}: {json.dumps(candidates, ensure_ascii=False)}")


SUMMARY_PROMPT = """You are a Google Maps review analyst for restaurant and cafe lending.

Given one matched business plus scraped Google reviews, produce a grounded review summary.
Use only the provided data. Do not invent facts.

Return ONLY JSON with this exact shape:
{
  "overall_sentiment": "positive" | "neutral" | "negative",
  "trend": "improving" | "stable" | "declining" | "mixed",
  "aspect_sentiment": {
    "food_quality": 0.0-1.0,
    "service": 0.0-1.0,
    "price": 0.0-1.0,
    "cleanliness": 0.0-1.0,
    "atmosphere": 0.0-1.0
  },
  "positive_themes": [up to 4 short phrases],
  "negative_themes": [up to 4 short phrases],
  "customer_profile": {
    "segments": [up to 3 values from: families, young_professionals, students, tourists, office_workers, regulars],
    "visit_reasons": [up to 3 short phrases],
    "loyalty_signal": "strong" | "moderate" | "weak",
    "estimated_daily_foot_traffic_band": "under_40" | "40-80" | "80-120" | "120-200" | "200+"
  },
  "red_flags": [up to 5 short snake_case values],
  "health_score": 0-100,
  "report_summary": "2-3 concise sentences"
}"""


def _actor_slug(actor_id: str) -> str:
    return actor_id.replace("/", "~")


async def _run_actor(actor_id: str, actor_input: dict[str, Any]) -> list[dict[str, Any]]:
    if not CONFIG.apify_token:
        raise GoogleReviewsError("APIFY_TOKEN is not configured")

    url = f"{CONFIG.apify_base_url}/acts/{_actor_slug(actor_id)}/run-sync-get-dataset-items"
    async with httpx.AsyncClient(timeout=CONFIG.apify_timeout_s) as client:
        resp = await client.post(url, params={"token": CONFIG.apify_token}, json=actor_input)
        resp.raise_for_status()
        body = resp.json()
    if not isinstance(body, list):
        raise GoogleReviewsError(f"Unexpected Apify response type from {actor_id}: {type(body).__name__}")
    return [item for item in body if isinstance(item, dict)]


def _normalize_name(value: str | None) -> str:
    text = (value or "").lower().strip()
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _unique_nonempty(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        norm = _normalize_name(value)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append((value or "").strip())
    return out


def _name_tokens(value: str | None) -> set[str]:
    return {tok for tok in _normalize_name(value).split() if len(tok) > 1 and tok not in _GENERIC_NAME_TOKENS}


def _search_strings(company_name: str) -> list[str]:
    raw = company_name.strip()
    brand_core = " ".join(tok for tok in re.findall(r"[\w\u0600-\u06FF]+", raw, flags=re.UNICODE) if _normalize_name(tok) not in _GENERIC_NAME_TOKENS)
    return _unique_nonempty([raw, brand_core]) or [company_name]


def _canonical_saudi_region(value: str | None) -> str | None:
    norm = _normalize_name(value)
    if not norm:
        return None
    return _SAUDI_REGION_ALIASES.get(norm, (value or "").strip())


def _location_query(city: str | None = None, district: str | None = None, region: str | None = None) -> str | None:
    parts = []
    for value in (district, city, _canonical_saudi_region(region)):
        cleaned = (value or "").strip()
        if cleaned and _normalize_name(cleaned) not in {_normalize_name(existing) for existing in parts}:
            parts.append(cleaned)
    if not parts:
        return None
    if _normalize_name("Saudi Arabia") not in {_normalize_name(existing) for existing in parts}:
        parts.append("Saudi Arabia")
    return ", ".join(parts)


def _location_queries(
    *,
    explicit_location_query: str | None = None,
    city: str | None = None,
    district: str | None = None,
    region: str | None = None,
) -> list[str]:
    hinted = any((explicit_location_query, city, district, region))
    return _unique_nonempty(
        [
            explicit_location_query,
            _location_query(city=city, district=district, region=region),
            _location_query(city=city, region=region),
            _location_query(city=city),
            _location_query(region=region),
            None if hinted else CONFIG.google_reviews_location_query,
        ],
    )


def _to_float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return None if value in (None, "") else int(value)
    except (TypeError, ValueError):
        return None


def _place_name(item: dict[str, Any]) -> str:
    for key in ("title", "name", "placeName"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _place_url(item: dict[str, Any]) -> str | None:
    for key in ("url", "placeUrl", "googleMapsUrl"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _build_place_url(company_name: str, google_place_id: str) -> str:
    query = quote(company_name or "business")
    return f"https://www.google.com/maps/search/?api=1&query={query}&query_place_id={google_place_id}"


def _cache_key(
    company_name: str,
    google_maps_url: str | None,
    *,
    city: str | None = None,
    district: str | None = None,
    region: str | None = None,
    location_query: str | None = None,
) -> str:
    parts = [
        _normalize_name(company_name),
        (google_maps_url or "").strip().lower(),
        _normalize_name(city),
        _normalize_name(district),
        _normalize_name(region),
        _normalize_name(location_query),
    ]
    return "|".join(parts)


def _get_cached_report(
    company_name: str,
    google_maps_url: str | None,
    *,
    city: str | None = None,
    district: str | None = None,
    region: str | None = None,
    location_query: str | None = None,
) -> dict[str, Any] | None:
    key = _cache_key(
        company_name,
        google_maps_url,
        city=city,
        district=district,
        region=region,
        location_query=location_query,
    )
    hit = _REPORT_CACHE.get(key)
    if not hit:
        return None
    expires_at, report = hit
    if expires_at <= datetime.now(UTC):
        _REPORT_CACHE.pop(key, None)
        return None
    return copy.deepcopy(report)


def _store_cached_report(
    company_name: str,
    google_maps_url: str | None,
    report: dict[str, Any],
    *,
    city: str | None = None,
    district: str | None = None,
    region: str | None = None,
    location_query: str | None = None,
) -> None:
    key = _cache_key(
        company_name,
        google_maps_url,
        city=city,
        district=district,
        region=region,
        location_query=location_query,
    )
    _REPORT_CACHE[key] = (datetime.now(UTC) + _REPORT_CACHE_TTL, copy.deepcopy(report))


def _candidate_match_score(
    company_name: str,
    item: dict[str, Any],
    google_maps_url: str | None = None,
    *,
    city: str | None = None,
    district: str | None = None,
) -> float:
    company_norm = _normalize_name(company_name)
    candidate_name = _place_name(item)
    candidate_norm = _normalize_name(candidate_name)
    company_tokens = _name_tokens(company_name)
    candidate_tokens = _name_tokens(candidate_name)

    score = 0.0
    if company_norm and candidate_norm:
        if company_norm == candidate_norm:
            score += 1.0
        if company_norm in candidate_norm or candidate_norm in company_norm:
            score += 0.75
    if company_tokens:
        score += (len(company_tokens & candidate_tokens) / len(company_tokens)) * 0.75
    if google_maps_url and _place_url(item) == google_maps_url:
        score += 1.0
    city_norm = _normalize_name(city)
    candidate_city_norm = _normalize_name(item.get("city"))
    if city_norm:
        if city_norm == candidate_city_norm:
            score += 1.0
        elif city_norm and candidate_city_norm:
            score -= 0.25
        elif city_norm in _normalize_name(item.get("address")):
            score += 0.75
    district_norm = _normalize_name(district)
    if district_norm:
        location_blob = _normalize_name(" ".join(str(item.get(key) or "") for key in ("neighborhood", "street", "address")))
        if district_norm in location_blob:
            score += 0.75
    if _to_int(item.get("reviewsCount")):
        score += min(math.log10((_to_int(item.get("reviewsCount")) or 0) + 1) / 5, 0.25)
    if item.get("temporarilyClosed") or item.get("permanentlyClosed"):
        score -= 0.5
    return round(score, 4)


def _candidate_city_matches(item: dict[str, Any], city: str | None) -> bool:
    city_norm = _normalize_name(city)
    if not city_norm:
        return False
    if city_norm == _normalize_name(item.get("city")):
        return True
    return city_norm in _normalize_name(item.get("address"))


def _candidate_district_matches(item: dict[str, Any], district: str | None) -> bool:
    district_norm = _normalize_name(district)
    if not district_norm:
        return False
    location_blob = _normalize_name(" ".join(str(item.get(key) or "") for key in ("neighborhood", "street", "address")))
    return district_norm in location_blob


def _top_candidates(
    ranked: list[tuple[dict[str, Any], float]],
    *,
    location_query: str | None = None,
) -> list[dict[str, Any]]:
    top: list[dict[str, Any]] = []
    for item, item_score in ranked[:5]:
        top.append(
            {
                "title": _place_name(item),
                "city": item.get("city"),
                "address": item.get("address"),
                "url": _place_url(item),
                "score": item_score,
                "location_query": location_query,
            },
        )
    return top


async def _resolve_place(
    company_name: str,
    google_maps_url: str | None,
    *,
    city: str | None = None,
    district: str | None = None,
    region: str | None = None,
    location_query: str | None = None,
) -> dict[str, Any]:
    if google_maps_url:
        return {"title": company_name, "url": google_maps_url, "match_score": 2.0}

    search_strings = _search_strings(company_name)
    fallback_ambiguity: list[dict[str, Any]] | None = None
    saw_candidates = False

    for search_location_query in _location_queries(
        explicit_location_query=location_query,
        city=city,
        district=district,
        region=region,
    ):
        items = await _run_actor(
            CONFIG.apify_places_actor_id,
            {
                "searchStringsArray": search_strings,
                "locationQuery": search_location_query,
                "countryCode": CONFIG.google_reviews_country_code.lower(),
                "language": CONFIG.google_reviews_language,
                "maxCrawledPlacesPerSearch": CONFIG.google_reviews_max_places,
                "searchMatching": "all",
                "skipClosedPlaces": True,
                "scrapePlaceDetailPage": False,
            },
        )

        deduped: dict[str, dict[str, Any]] = {}
        for item in items:
            place_url = _place_url(item)
            if not place_url:
                continue
            key = str(item.get("placeId") or place_url)
            existing = deduped.get(key)
            if not existing or (_to_int(item.get("reviewsCount")) or 0) > (_to_int(existing.get("reviewsCount")) or 0):
                deduped[key] = item

        candidate_items = list(deduped.values())
        if city:
            city_matches = [item for item in candidate_items if _candidate_city_matches(item, city)]
            if city_matches:
                candidate_items = city_matches
        if district:
            district_matches = [item for item in candidate_items if _candidate_district_matches(item, district)]
            if district_matches:
                candidate_items = district_matches

        ranked: list[tuple[dict[str, Any], float]] = []
        for item in candidate_items:
            ranked.append(
                (
                    item,
                    _candidate_match_score(
                        company_name,
                        item,
                        city=city,
                        district=district,
                    ),
                ),
            )
        if not ranked:
            continue
        saw_candidates = True

        ranked.sort(key=lambda pair: pair[1], reverse=True)
        best, score = ranked[0]
        if score < 0.6:
            continue
        if len(ranked) > 1:
            _, second_score = ranked[1]
            if (score - second_score) <= 0.15:
                fallback_ambiguity = _top_candidates(ranked, location_query=search_location_query)
                continue
        best = dict(best)
        best["match_score"] = score
        best["matched_location_query"] = search_location_query
        return best

    if fallback_ambiguity:
        raise GooglePlaceAmbiguous(company_name, fallback_ambiguity)
    if saw_candidates:
        raise GooglePlaceNotFound(f"No strong Google Maps match found for {company_name}")
    raise GooglePlaceNotFound(f"No Google Maps place candidates found for {company_name}")


def _persist_place_resolution(merchant_id: str | None, place: dict[str, Any]) -> None:
    if not merchant_id:
        return
    place_id = place.get("place_id") or place.get("placeId")
    place_url = place.get("url")
    if not place_id and not place_url:
        return
    payload = {"google_place_resolved_at": datetime.now(UTC).isoformat()}
    if place_id:
        payload["google_place_id"] = place_id
    if place_url:
        payload["google_place_url"] = place_url
    if place.get("title"):
        payload["google_place_title"] = place.get("title")
    if place.get("address"):
        payload["google_place_address"] = place.get("address")
    try:
        get_client().table("merchants").update(payload).eq("id", merchant_id).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("merchant google place persist failed", extra={"merchant_id": merchant_id, "err": str(e)[:300]})


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _normalize_review(item: dict[str, Any]) -> dict[str, Any]:
    published = None
    for key in ("publishedAtDate", "publishedAt", "reviewedAt", "date"):
        published = _parse_datetime(item.get(key))
        if published:
            break
    return {
        "review_id": item.get("reviewId") or item.get("id"),
        "review_url": item.get("reviewUrl") or item.get("url"),
        "rating": _to_float(item.get("stars") or item.get("rating")),
        "text": (item.get("text") or item.get("textTranslated") or item.get("reviewText") or "").strip(),
        "published_at": published.isoformat() if published else None,
        "response_from_owner_text": (item.get("responseFromOwnerText") or item.get("ownerResponseText") or "").strip() or None,
        "reviewer_number_of_reviews": _to_int(item.get("reviewerNumberOfReviews") or item.get("numberOfReviewsByReviewer")),
        "is_local_guide": bool(item.get("isLocalGuide")) if item.get("isLocalGuide") is not None else None,
        "review_origin": item.get("reviewOrigin") or "google",
    }


def _extract_review_rows(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    place_meta: dict[str, Any] = {}
    for item in items:
        if not place_meta:
            place_meta = {
                "title": item.get("title") or item.get("placeName") or item.get("name"),
                "url": item.get("placeUrl") or item.get("url") or item.get("googleMapsUrl"),
                "place_id": item.get("placeId"),
                "total_score": _to_float(item.get("totalScore") or item.get("rating")),
                "reviews_count": _to_int(item.get("reviewsCount")),
                "address": item.get("address"),
            }
        if any(k in item for k in ("reviewId", "reviewUrl", "responseFromOwnerText", "publishedAtDate", "stars", "reviewText")):
            reviews.append(_normalize_review(item))
            continue
        nested = item.get("reviews")
        if isinstance(nested, list):
            for review in nested:
                if isinstance(review, dict):
                    reviews.append(_normalize_review(review))
    reviews = [r for r in reviews if r.get("rating") is not None or r.get("text")]
    reviews.sort(key=lambda r: r.get("published_at") or "", reverse=True)
    return reviews, place_meta


def _keyword_flags(reviews: list[dict[str, Any]]) -> list[str]:
    text = " ".join((r.get("text") or "").lower() for r in reviews)
    flags = []
    keyword_map = {
        "food_safety_mentions": ["food poisoning", "made me sick", "sick after", "stomach"],
        "cleanliness_concerns": ["dirty", "unclean", "cockroach", "insect", "bathroom dirty"],
        "service_breakdown": ["rude", "ignored", "slow service", "waited", "overwhelmed"],
        "pricing_backlash": ["overpriced", "too pricey", "price increased", "expensive"],
        "closure_or_decline": ["used to be better", "declined", "closed", "shut down"],
    }
    for flag, phrases in keyword_map.items():
        if any(phrase in text for phrase in phrases):
            flags.append(flag)
    return flags


def _review_metrics(reviews: list[dict[str, Any]], place: dict[str, Any]) -> dict[str, Any]:
    ratings = [r["rating"] for r in reviews if r.get("rating") is not None]
    average_review_stars = round(sum(ratings) / len(ratings), 2) if ratings else None
    now = datetime.now(UTC)
    parsed_dates = [datetime.fromisoformat(r["published_at"]) for r in reviews if r.get("published_at")]
    last_review_days_ago = min(max((now - dt).days, 0) for dt in parsed_dates) if parsed_dates else None
    review_velocity_30d = sum(1 for dt in parsed_dates if (now - dt).days <= 30) if parsed_dates else None
    owner_response_rate = round(sum(1 for r in reviews if r.get("response_from_owner_text")) / len(reviews), 3) if reviews else 0.0
    return {
        "average_review_stars": average_review_stars,
        "last_review_days_ago": last_review_days_ago,
        "review_velocity_30d": review_velocity_30d,
        "owner_response_rate": owner_response_rate,
        "reviews_sampled": len(reviews),
        "place_reviews_count": place.get("reviews_count"),
    }


def _deterministic_summary(company_name: str, place: dict[str, Any], reviews: list[dict[str, Any]]) -> dict[str, Any]:
    ratings = [r["rating"] for r in reviews if r.get("rating") is not None]
    avg_review_stars = round(sum(ratings) / len(ratings), 2) if ratings else None
    review_count = place.get("reviews_count") or len(reviews)
    negative_share = (sum(1 for r in ratings if r <= 2) / len(ratings)) if ratings else 0.0
    owner_response_rate = (sum(1 for r in reviews if r.get("response_from_owner_text")) / len(reviews)) if reviews else 0.0
    red_flags = _keyword_flags(reviews)
    place_total_score = place.get("total_score")

    rating_baseline = avg_review_stars
    if place_total_score is not None:
        if rating_baseline is None:
            rating_baseline = place_total_score
        elif len(ratings) < 10 or (review_count and review_count > len(ratings) * 10 and abs(rating_baseline - place_total_score) > 0.4):
            rating_baseline = place_total_score

    if rating_baseline is None:
        sentiment = "neutral"
    elif rating_baseline >= 4.2 and negative_share < 0.18:
        sentiment = "positive"
    elif rating_baseline >= 3.6:
        sentiment = "neutral"
    else:
        sentiment = "negative"

    trend = "stable"
    if reviews and len(ratings) >= 6:
        recent = [r["rating"] for r in reviews[:10] if r.get("rating") is not None]
        older = [r["rating"] for r in reviews[10:] if r.get("rating") is not None]
        if recent and older:
            delta = (sum(recent) / len(recent)) - (sum(older) / len(older))
            if delta > 0.25:
                trend = "improving"
            elif delta < -0.25:
                trend = "declining"

    base_score = (rating_baseline or 3.5) * 20
    base_score += min(math.log10(max(review_count, 1)) * 8, 10)
    base_score -= negative_share * 18
    base_score += owner_response_rate * 4
    base_score -= len(red_flags) * 7
    health_score = max(0, min(100, round(base_score)))

    summary = (
        f"{place.get('title') or company_name} shows {sentiment} Google review health at "
        f"{rating_baseline or 0:.1f}/5 across {review_count} reviews. "
        f"Trend looks {trend}."
    )
    if len(reviews) >= 10:
        summary += f" Sampled owner response rate is {round(owner_response_rate * 100)}%."
    if red_flags:
        summary += f" Main concerns: {', '.join(red_flags[:2])}."

    return {
        "overall_sentiment": sentiment,
        "trend": trend,
        "aspect_sentiment": {
            "food_quality": 0.65 if sentiment == "positive" else 0.45,
            "service": 0.35 if "service_breakdown" in red_flags else 0.6,
            "price": 0.3 if "pricing_backlash" in red_flags else 0.5,
            "cleanliness": 0.25 if "cleanliness_concerns" in red_flags else 0.6,
            "atmosphere": 0.55,
        },
        "positive_themes": [],
        "negative_themes": red_flags[:4],
        "customer_profile": {
            "segments": [],
            "visit_reasons": [],
            "loyalty_signal": "moderate" if review_count >= 50 else "weak",
            "estimated_daily_foot_traffic_band": "40-80" if review_count >= 50 else "under_40",
        },
        "red_flags": red_flags,
        "health_score": health_score,
        "report_summary": summary,
    }


async def _llm_summary(loan_id: str, company_name: str, place: dict[str, Any], reviews: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any] | None:
    payload = {
        "company_name": company_name,
        "place": place,
        "metrics": metrics,
        "reviews": reviews[: min(len(reviews), 40)],
    }
    try:
        parsed, _ = await traced_llm_call(
            loan_id=loan_id,
            stage="google_reviews_summary",
            dimension="sentiment",
            system=SUMMARY_PROMPT,
            user="Context:\n```json\n" + json.dumps(payload, ensure_ascii=False, default=str) + "\n```",
            json_mode=True,
        )
        return parsed if isinstance(parsed, dict) else None
    except Exception as e:  # noqa: BLE001
        log.warning("google reviews llm summary failed", extra={"err": str(e)[:300]})
        return None


async def build_google_review_report(
    *,
    loan_id: str,
    company_name: str,
    google_maps_url: str | None = None,
    google_place_id: str | None = None,
    google_place_url: str | None = None,
    merchant_id: str | None = None,
    city: str | None = None,
    district: str | None = None,
    region: str | None = None,
    location_query: str | None = None,
) -> dict[str, Any]:
    """Resolve a business and return a structured Google review report."""
    exact_url = (google_place_url or google_maps_url or "").strip() or None
    if not exact_url and google_place_id:
        exact_url = _build_place_url(company_name, google_place_id)

    cached = _get_cached_report(
        company_name,
        exact_url,
        city=city,
        district=district,
        region=region,
        location_query=location_query,
    )
    if cached is not None:
        write_event(
            loan_id=loan_id,
            stage="google_reviews_cache_hit",
            dimension="sentiment",
            kind="aggregation",
            parsed={"company_name": company_name},
        )
        return cached

    if exact_url:
        place = {
            "title": company_name,
            "url": exact_url,
            "placeId": google_place_id,
            "match_score": 2.0,
        }
    else:
        place = await _resolve_place(
            company_name,
            None,
            city=city,
            district=district,
            region=region,
            location_query=location_query,
        )
    place_url = _place_url(place)
    if not place_url:
        raise GooglePlaceNotFound(f"Matched place has no URL for {company_name}")

    review_actor_input: dict[str, Any] = {
        "maxReviews": CONFIG.google_reviews_max_reviews,
        "reviewsSort": "newest",
        "reviewsOrigin": "google",
        "personalData": False,
        "language": CONFIG.google_reviews_language,
    }
    if place.get("placeId") or place.get("place_id"):
        review_actor_input["placeIds"] = [place.get("placeId") or place.get("place_id")]
    else:
        review_actor_input["startUrls"] = [{"url": place_url}]
    review_items = await _run_actor(CONFIG.apify_reviews_actor_id, review_actor_input)

    reviews, review_place_meta = _extract_review_rows(review_items)
    place = {
        "title": review_place_meta.get("title") or place.get("title"),
        "url": review_place_meta.get("url") or place_url,
        "place_id": review_place_meta.get("place_id") or place.get("placeId"),
        "total_score": review_place_meta.get("total_score") if review_place_meta.get("total_score") is not None else _to_float(place.get("totalScore")),
        "reviews_count": review_place_meta.get("reviews_count") if review_place_meta.get("reviews_count") is not None else _to_int(place.get("reviewsCount")),
        "address": review_place_meta.get("address") or place.get("address"),
        "match_score": place.get("match_score"),
        "matched_location_query": place.get("matched_location_query"),
    }
    metrics = _review_metrics(reviews, place)
    summary = await _llm_summary(loan_id, company_name, place, reviews, metrics) or _deterministic_summary(company_name, place, reviews)

    report = {
        "company_name": company_name,
        "place": place,
        "google_rating": place.get("total_score"),
        "review_count": place.get("reviews_count") or len(reviews),
        "review_velocity_30d": metrics.get("review_velocity_30d"),
        "last_review_days_ago": metrics.get("last_review_days_ago"),
        "average_review_stars": metrics.get("average_review_stars"),
        "owner_response_rate": metrics.get("owner_response_rate"),
        "overall_sentiment": summary.get("overall_sentiment"),
        "trend": summary.get("trend"),
        "aspect_sentiment": summary.get("aspect_sentiment") or {},
        "positive_themes": summary.get("positive_themes") or [],
        "negative_themes": summary.get("negative_themes") or [],
        "customer_profile": summary.get("customer_profile") or {},
        "red_flags": summary.get("red_flags") or [],
        "health_score": float(summary.get("health_score") or 50.0),
        "report_summary": summary.get("report_summary") or f"Google review summary unavailable for {company_name}.",
        "business_identity_match": bool((place.get("match_score") or 0) >= 0.6),
        "scraped_successfully": True,
        "confidence": 0.8 if reviews else 0.55,
        "sample_reviews": reviews[:5],
        "flags": list(dict.fromkeys((summary.get("red_flags") or []) + ([] if reviews else ["no_reviews_scraped"]))),
    }

    write_event(
        loan_id=loan_id,
        stage="google_reviews_report_built",
        dimension="sentiment",
        kind="aggregation",
        parsed={
            "place_title": report["place"].get("title"),
            "review_count": report["review_count"],
            "health_score": report["health_score"],
            "flags": report["flags"],
        },
    )
    _persist_place_resolution(merchant_id, report["place"])
    _store_cached_report(
        company_name,
        exact_url,
        report,
        city=city,
        district=district,
        region=region,
        location_query=location_query,
    )
    return report

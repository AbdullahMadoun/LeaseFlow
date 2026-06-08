"""Sentiment dim backed by the Google Maps reviews agent."""
from __future__ import annotations

from ..google_reviews_agent import GooglePlaceAmbiguous, GooglePlaceNotFound, build_google_review_report
from ..schemas import DimensionOutput


async def run(ctx: dict) -> DimensionOutput:
    merchant = ctx["merchant"]
    loan_id = str(ctx["loan"]["id"])
    business_name = merchant["business_name"]

    try:
        report = await build_google_review_report(
            loan_id=loan_id,
            company_name=business_name,
            google_maps_url=merchant.get("google_maps_url"),
            google_place_id=merchant.get("google_place_id"),
            google_place_url=merchant.get("google_place_url"),
            merchant_id=str(merchant["id"]),
            city=merchant.get("city"),
            district=merchant.get("district"),
            region=merchant.get("region"),
            location_query=merchant.get("google_reviews_location_query"),
        )
    except GooglePlaceAmbiguous:
        return DimensionOutput(
            dimension="sentiment",
            score=50.0,
            confidence=0.0,
            narrative=f"Multiple Google Maps places matched {business_name}; a direct Maps URL is required.",
            features={
                "query_company_name": business_name,
                "business_identity_match": False,
                "scraped_successfully": False,
            },
            flags=["google_place_ambiguous"],
            dimension_version="sentiment@apify-v1",
        )
    except GooglePlaceNotFound:
        return DimensionOutput(
            dimension="sentiment",
            score=50.0,
            confidence=0.0,
            narrative=f"No Google Maps place matched for {business_name}.",
            features={
                "query_company_name": business_name,
                "business_identity_match": False,
                "scraped_successfully": False,
            },
            flags=["google_place_not_found"],
            dimension_version="sentiment@apify-v1",
        )

    return DimensionOutput(
        dimension="sentiment",
        score=float(report["health_score"]),
        confidence=float(report["confidence"]),
        narrative=report["report_summary"][:300],
        features={
            "google_rating": report.get("google_rating"),
            "review_count": report.get("review_count"),
            "review_velocity_30d": report.get("review_velocity_30d"),
            "last_review_days_ago": report.get("last_review_days_ago"),
            "overall_sentiment": report.get("overall_sentiment"),
            "trend": report.get("trend"),
            "aspect_sentiment": report.get("aspect_sentiment") or {},
            "positive_themes": report.get("positive_themes") or [],
            "negative_themes": report.get("negative_themes") or [],
            "customer_profile": report.get("customer_profile") or {},
            "red_flags": report.get("red_flags") or [],
            "business_identity_match": report.get("business_identity_match", False),
            "scraped_successfully": report.get("scraped_successfully", False),
            "place": report.get("place") or {},
            "sample_reviews": report.get("sample_reviews") or [],
            "owner_response_rate": report.get("owner_response_rate"),
            "average_review_stars": report.get("average_review_stars"),
        },
        flags=report.get("flags") or [],
        dimension_version="sentiment@apify-v1",
    )

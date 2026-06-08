"""Industry dim.

Pipeline:
  1. Classify the merchant's F&B segment via MiniMax (closed list).
  2. Look up benchmarks from the `segments` table (seeded from fnb-benchmarks).
  3. Resolve approximate location (mock for demo — prod would use Places API).
  4. Mock local competition density.
  5. MiniMax produces a 1-sentence narrative.

Falls back to deterministic output if LLM unavailable.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging

from ..schemas import DimensionOutput
from ..supabase_client import get_client
from ..tracing import traced_llm_call

log = logging.getLogger(__name__)

SEGMENTS = [
    "specialty_coffee", "qsr", "casual_dining", "fine_dining",
    "bakery", "juice_bar", "dessert_parlor", "cloud_kitchen",
    "food_truck", "other_fnb",
]

SEGMENT_LABELS = {
    "specialty_coffee": "Specialty coffee / counter-service café",
    "qsr": "Quick-service restaurant",
    "casual_dining": "Casual / full-service restaurant",
    "fine_dining": "Fine dining",
    "bakery": "Bakery / patisserie",
    "juice_bar": "Juice bar / healthy grab-and-go",
    "dessert_parlor": "Dessert parlor / ice cream",
    "cloud_kitchen": "Cloud / delivery-only kitchen",
    "food_truck": "Food truck / mobile",
    "other_fnb": "Other F&B",
}


def _seed(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


CLASSIFY_PROMPT = """You are classifying a KSA F&B merchant into a closed segment list.

Given a business name (often in Arabic or English or both) and a commercial
registration number, pick ONE segment from this list:

""" + "\n".join(f"- {k}: {v}" for k, v in SEGMENT_LABELS.items()) + """

Return ONLY JSON: {"segment": "<one of the keys above>", "rationale": "1 short sentence"}.
If genuinely ambiguous, return "other_fnb"."""


async def _classify(business_name: str, cr_number: str, loan_id: str) -> str | None:
    user = f"Business: {business_name}\nCR number: {cr_number}\n\nPick the segment."
    try:
        out, _ = await traced_llm_call(
            loan_id=loan_id, stage="dim_industry_classify", dimension="industry",
            system=CLASSIFY_PROMPT, user=user, json_mode=True,
        )
        seg = out.get("segment")
        if seg in SEGMENTS:
            return seg
    except Exception as e:  # noqa: BLE001
        log.warning("industry classify failed", extra={"err": str(e)})
    return None


NARRATIVE_PROMPT = """You write a one-sentence narrative about a KSA F&B business's
industry context. Given segment, location, competition density, and macro trend,
produce a single sentence (≤25 words) that combines them.

Return ONLY JSON: {"narrative": "..."}."""


async def _narrative(segment_label: str, city: str, density: str, growth: float,
                     cost_trend: str, loan_id: str) -> str | None:
    user = (
        f"Segment: {segment_label}\n"
        f"City: {city}\n"
        f"Local competition density: {density}\n"
        f"Segment growth YoY: {int(growth*100)}%\n"
        f"Input cost trend: {cost_trend}\n"
    )
    try:
        out, _ = await traced_llm_call(
            loan_id=loan_id, stage="dim_industry_narrative", dimension="industry",
            system=NARRATIVE_PROMPT, user=user, json_mode=True,
        )
        return (out.get("narrative") or "").strip() or None
    except Exception as e:  # noqa: BLE001
        log.warning("industry narrative failed", extra={"err": str(e)})
    return None


async def run(ctx: dict) -> DimensionOutput:
    merchant = ctx["merchant"]
    loan_id = str(ctx["loan"]["id"])
    name = merchant["business_name"]
    cr = merchant.get("cr_number", "")
    s = _seed(name)
    await asyncio.sleep(0.2)

    # 1. Segment — LLM first, fallback to hash
    segment = await _classify(name, cr, loan_id)
    if segment is None:
        segment = SEGMENTS[s % len(SEGMENTS)]

    # 2. Benchmarks
    sb = get_client()
    seg_row = sb.table("segments").select("label, benchmarks").eq("name", segment).execute()
    benchmarks = seg_row.data[0]["benchmarks"] if seg_row.data else {}
    label = seg_row.data[0]["label"] if seg_row.data else SEGMENT_LABELS.get(segment, segment)

    # 3. Location (mock — deterministic by business name)
    cities = ["Riyadh", "Jeddah", "Dammam", "Mecca", "Medina", "Khobar"]
    districts = ["Al Olaya", "Al Malqa", "Al Rawda", "Downtown", "King Abdullah Rd."]
    city = cities[s % len(cities)]
    district = districts[(s >> 3) % len(districts)]

    # 4. Competition density (mock)
    competitor_count = 3 + (s % 20)
    density = "low" if competitor_count < 6 else ("medium" if competitor_count < 14 else "high")
    avg_competitor_rating = round(3.5 + ((s >> 5) % 15) / 10, 1)

    # 5. Macro trends
    growth_yoy = round(0.03 + ((s >> 7) % 12) / 100, 2)
    input_cost_trend = ["stable", "rising", "falling"][(s >> 9) % 3]

    # Score: simple heuristic over density + growth + cost trend
    score = 60
    if density == "low":
        score += 10
    if density == "high":
        score -= 10
    if growth_yoy >= 0.08:
        score += 8
    if input_cost_trend == "rising":
        score -= 5
    score = max(20, min(95, score))

    flags = []
    if density == "high":
        flags.append("high_local_competition")
    if input_cost_trend == "rising":
        flags.append("rising_input_costs")

    # Narrative via LLM, fallback to template
    narrative = await _narrative(label, city, density, growth_yoy, input_cost_trend, loan_id)
    if not narrative:
        narrative = f"{label} in {city} / {district}; {density} competition; segment growth {int(growth_yoy*100)}% YoY."

    return DimensionOutput(
        dimension="industry",
        score=float(score),
        confidence=0.60,
        narrative=narrative[:300],
        features={
            "segment": segment,
            "segment_label": label,
            "location": {"city": city, "district": district},
            "local_competition": {
                "similar_within_1km": competitor_count,
                "avg_competitor_rating": avg_competitor_rating,
                "density": density,
            },
            "segment_benchmarks": benchmarks,
            "macro": {
                "segment_growth_yoy": growth_yoy,
                "input_cost_trend": input_cost_trend,
                "regulatory_risk": "low",
            },
        },
        flags=flags,
        dimension_version="industry@llm-v1",
    )

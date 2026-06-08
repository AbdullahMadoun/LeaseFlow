"""SIMAH dim — STUB.

Replace with real SIMAH API integration. Cache in public.simah_cache keyed by
cr_number with 24h TTL (already done below).
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone

from ..schemas import DimensionOutput
from ..supabase_client import get_client


def _seed(cr: str) -> int:
    return int(hashlib.sha256(cr.encode()).hexdigest()[:8], 16)


def _generate(cr_number: str) -> dict:
    s = _seed(cr_number)
    credit_score = 450 + (s % 400)  # 450..849
    active_count = s % 4
    active_total = active_count * (30000 + (s % 80000))
    defaults_count = 1 if s % 20 == 0 else 0  # ~5% default rate
    recent_inquiries = s % 5

    if credit_score >= 720 and defaults_count == 0:
        rec, pay, score = "approve", "excellent", 85
    elif credit_score >= 650 and defaults_count == 0:
        rec, pay, score = "caution", "good", 70
    elif credit_score >= 580 and defaults_count == 0:
        rec, pay, score = "caution", "fair", 50
    else:
        rec, pay, score = "deny", "poor", 25

    return {
        "credit_score": credit_score,
        "active_facilities_count": active_count,
        "active_facilities_total_sar": active_total,
        "defaults_count": defaults_count,
        "payment_history": pay,
        "recent_inquiries_90d": recent_inquiries,
        "simah_recommendation": rec,
        "_score": score,
    }


async def run(ctx: dict) -> DimensionOutput:
    merchant = ctx["merchant"]
    cr = merchant["cr_number"]
    sb = get_client()

    # Cache lookup (24h TTL)
    now = datetime.now(timezone.utc)
    cached = sb.table("simah_cache").select("result, cached_until").eq("cr_number", cr).execute()
    if cached.data:
        row = cached.data[0]
        until = row["cached_until"]
        if isinstance(until, str):
            until = datetime.fromisoformat(until.replace("Z", "+00:00"))
        if until > now:
            features = row["result"]
            score = features.pop("_score", 60)
            return _to_output(features, score)

    # Simulate real API call
    await asyncio.sleep(1.2)
    features = _generate(cr)
    sb.table("simah_cache").upsert({
        "cr_number": cr,
        "result": features,
        "cached_until": (now + timedelta(hours=24)).isoformat(),
    }).execute()
    score = features.pop("_score", 60)
    return _to_output(features, score)


def _to_output(features: dict, score: int) -> DimensionOutput:
    pay = features.get("payment_history", "?")
    defaults = features.get("defaults_count", 0)
    cs = features.get("credit_score", 0)
    narrative = f"SIMAH score {cs}, {defaults} default(s), payment history {pay}."
    flags = []
    if defaults > 0:
        flags.append("simah_defaults_present")
    if features.get("recent_inquiries_90d", 0) >= 4:
        flags.append("high_recent_inquiries")
    return DimensionOutput(
        dimension="simah",
        score=float(score),
        confidence=0.95,
        narrative=narrative,
        features=features,
        flags=flags,
        dimension_version="simah@stub-v1",
    )

"""POS dim aggregator.

Reads per-document POSReport instances from documents.analysis_report,
combines daily arrays across multiple CSVs if uploaded, computes
operational health score, fires one LLM narrative call.
"""
from __future__ import annotations

import logging

from ..schemas import DimensionOutput
from ..tracing import traced_llm_call

log = logging.getLogger(__name__)

NARRATIVE_PROMPT = """You write a 1-2 sentence (≤40 words) narrative describing a merchant's
POS operational health for a lease-to-own decision. Specific, number-tied, no hedging.

Return ONLY JSON: {"narrative": "..."}."""


async def _narrative(loan_id: str, features: dict) -> str:
    try:
        import json as _json
        parsed, _ = await traced_llm_call(
            loan_id=loan_id, stage="dim_pos_narrative", dimension="pos",
            system=NARRATIVE_PROMPT,
            user="Features:\n```json\n" + _json.dumps(features, default=str) + "\n```",
            json_mode=True,
        )
        return (parsed.get("narrative") or "").strip()[:300]
    except Exception as e:  # noqa: BLE001
        log.warning("pos narrative failed, using template", extra={"err": str(e)})
        agg = features.get("aggregates") or {}
        return (f"Avg ticket {agg.get('avg_ticket_sar', 0):.0f} SAR, "
                f"~{agg.get('daily_revenue_avg_sar', 0):,.0f} SAR/day, "
                f"trend {agg.get('trend_90d') or 'n/a'}.")


def _aggregate_pos(reports: list[dict]) -> dict:
    if not reports:
        return {"present": False}
    # Combine aggregates from multiple reports by weighted average on txn_count
    agg_fields = ["daily_revenue_avg_sar", "avg_ticket_sar", "void_rate", "refund_rate"]
    totals: dict[str, float] = {f: 0 for f in agg_fields}
    weights: dict[str, float] = {f: 0 for f in agg_fields}
    trends: list[str] = []
    seasonalities: list[str] = []
    peak_hours: list[str] = []
    cash_mix_total: float = 0
    cash_mix_weight: float = 0

    for r in reports:
        daily = r.get("daily") or []
        txn_sum = sum(d.get("txn_count", 0) for d in daily) or 1
        a = r.get("aggregates") or {}
        for f in agg_fields:
            v = a.get(f)
            if v is not None:
                totals[f] += v * txn_sum
                weights[f] += txn_sum
        if a.get("trend_90d"):
            trends.append(a["trend_90d"])
        if a.get("seasonality"):
            seasonalities.append(a["seasonality"])
        if a.get("peak_hours"):
            peak_hours.extend(a["peak_hours"])
        if a.get("cash_card_mix") and a["cash_card_mix"].get("cash") is not None:
            cash_mix_total += a["cash_card_mix"]["cash"] * txn_sum
            cash_mix_weight += txn_sum

    out = {
        "present": True,
        "report_count": len(reports),
        "trend": trends[-1] if trends else None,  # most recent report
        "seasonality": seasonalities[-1] if seasonalities else None,
        "peak_hours": list(dict.fromkeys(peak_hours))[:2],
    }
    for f in agg_fields:
        out[f] = round(totals[f] / weights[f], 4) if weights[f] else None
    if out.get("daily_revenue_avg_sar") is not None:
        out["monthly_revenue_est_sar"] = round(out["daily_revenue_avg_sar"] * 30, 2)
    if cash_mix_weight:
        cash = cash_mix_total / cash_mix_weight
        out["cash_card_mix"] = {"cash": round(cash, 2), "card": round(1 - cash, 2)}
    return out


async def run(ctx: dict) -> DimensionOutput:
    loan = ctx["loan"]
    docs = ctx.get("documents") or []
    loan_id = str(loan["id"])

    pos_reports = [
        d["analysis_report"] for d in docs
        if d["doc_type"] == "pos_data"
        and d.get("analysis_status") == "done"
        and d.get("analysis_report")
        and not (d["analysis_report"] or {}).get("error")
    ]

    if not pos_reports:
        return DimensionOutput(
            dimension="pos", score=0, confidence=0.0,
            narrative="No POS data available.",
            features={}, flags=["no_pos_data"],
            dimension_version="pos@agg-v1",
        )

    agg = _aggregate_pos(pos_reports)

    # Score: base 65; +/- based on operational signals
    score = 65.0
    flags: list[str] = []
    vr = agg.get("void_rate")
    if vr is not None:
        if vr > 0.025: score -= 12; flags.append("high_void_rate")
        elif vr < 0.015: score += 5
    rr = agg.get("refund_rate")
    if rr is not None and rr > 0.015:
        score -= 8
        flags.append("high_refund_rate")
    trend = agg.get("trend")
    if trend in ("up", "slightly_up"):
        score += 8
    elif trend in ("down", "slightly_down"):
        score -= 8
    cash = (agg.get("cash_card_mix") or {}).get("cash")
    if cash is not None and cash > 0.40:
        flags.append("cash_heavy_mix")
    score = max(0.0, min(100.0, score))
    confidence = 0.85 if agg.get("report_count", 0) >= 1 else 0.5

    features = {
        "aggregates": agg,
        "daily_revenue_avg_sar": agg.get("daily_revenue_avg_sar"),
        "monthly_revenue_est_sar": agg.get("monthly_revenue_est_sar"),
        "avg_ticket_sar": agg.get("avg_ticket_sar"),
        "peak_hours": agg.get("peak_hours"),
        "seasonality": agg.get("seasonality"),
        "void_rate": agg.get("void_rate"),
        "refund_rate": agg.get("refund_rate"),
        "cash_card_mix": agg.get("cash_card_mix"),
        "trend_90d": agg.get("trend"),
        "source_document_count": len(pos_reports),
    }

    narrative = await _narrative(loan_id, features)

    return DimensionOutput(
        dimension="pos",
        score=score, confidence=confidence, narrative=narrative,
        features=features, flags=flags,
        dimension_version="pos@agg-v1",
    )

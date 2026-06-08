"""Financial dim aggregator.

Reads per-document reports from documents.analysis_report (populated in
Phase A), combines, reconciles bank vs income statement, computes DSCR
deterministically, fires one LLM call for a narrative.
"""
from __future__ import annotations

import logging

from ..schemas import DimensionOutput
from ..tracing import traced_llm_call, write_event

log = logging.getLogger(__name__)


def _dscr(amount: float, profit_rate: float, months: int, monthly_net: float | None) -> dict:
    total_due = amount * (1 + profit_rate)
    proposed = total_due / months if months > 0 else 0
    dscr = None
    cat = "unknown"
    if monthly_net is not None and proposed > 0:
        dscr = monthly_net / proposed
        if dscr >= 1.5: cat = "comfortable"
        elif dscr >= 1.2: cat = "marginal"
        elif dscr >= 1.0: cat = "marginal"
        else: cat = "risky"
    return {
        "amount_requested": amount,
        "profit_rate": profit_rate,
        "repayment_months": months,
        "total_due": round(total_due, 2),
        "proposed_monthly_payment": round(proposed, 2),
        "dscr": round(dscr, 2) if dscr is not None else None,
        "dscr_category": cat,
    }


def _aggregate_bank_statements(reports: list[dict]) -> dict:
    if not reports:
        return {"present": False}
    all_months: list[dict] = []
    for r in reports:
        all_months.extend(r.get("monthly") or [])
    if not all_months:
        return {"present": True, "monthly_net_avg_sar": None, "reports": len(reports)}
    nets = [m["net_sar"] for m in all_months if m.get("net_sar") is not None]
    revs = [m["revenue_sar"] for m in all_months if m.get("revenue_sar") is not None]
    exps = [m["expenses_sar"] for m in all_months if m.get("expenses_sar") is not None]
    mean_net = sum(nets) / max(1, len(nets))
    std = (sum((n - mean_net) ** 2 for n in nets) / max(1, len(nets))) ** 0.5
    vol = std / max(1, abs(mean_net)) if nets else None
    half = len(nets) // 2
    first = sum(nets[:half]) / max(1, half) if half else None
    second = sum(nets[half:]) / max(1, len(nets) - half) if nets else None
    delta = ((second - first) / max(1, abs(first))) if first else 0
    trend = "up" if delta > 0.05 else ("down" if delta < -0.05 else "stable")
    bounced = sum((r.get("aggregates") or {}).get("bounced_count", 0) or 0 for r in reports)
    overdrafts = sum((r.get("aggregates") or {}).get("overdraft_events", 0) or 0 for r in reports)
    return {
        "present": True,
        "reports": len(reports),
        "monthly_count": len(all_months),
        "monthly_revenue_avg_sar": round(sum(revs) / max(1, len(revs)), 2) if revs else None,
        "monthly_expenses_avg_sar": round(sum(exps) / max(1, len(exps)), 2) if exps else None,
        "monthly_net_avg_sar": round(mean_net, 2) if nets else None,
        "volatility": round(vol, 3) if vol is not None else None,
        "trend": trend,
        "bounced_count": bounced,
        "overdraft_events": overdrafts,
    }


def _extract_financial_statement(reports: list[dict]) -> dict:
    if not reports:
        return {"present": False}
    r = reports[0]
    return {
        "present": True,
        "balance_sheet": r.get("balance_sheet") or {},
        "income_statement": r.get("income_statement") or {},
        "ratios": r.get("ratios") or {},
    }


def _reconcile(bank: dict, fin: dict) -> dict:
    if not (bank.get("present") and fin.get("present")):
        return {"possible": False}
    bank_rev_annual = (bank.get("monthly_revenue_avg_sar") or 0) * 12
    stmt_rev = (fin.get("income_statement") or {}).get("revenue_sar") or 0
    if not bank_rev_annual or not stmt_rev:
        return {"possible": False}
    delta_pct = (bank_rev_annual - stmt_rev) / max(1, stmt_rev)
    return {
        "possible": True,
        "bank_annualised_revenue_sar": round(bank_rev_annual, 2),
        "statement_revenue_sar": round(stmt_rev, 2),
        "delta_pct": round(delta_pct, 3),
        "consistent": abs(delta_pct) < 0.15,
    }


NARRATIVE_PROMPT = """You write a 1-2 sentence (≤40 words) narrative describing a merchant's
financial health for a lease-to-own decision. Be specific, number-tied, no hedging.

Return ONLY JSON: {"narrative": "..."}."""


async def _narrative(loan_id: str, features: dict) -> str:
    try:
        import json as _json
        parsed, _ = await traced_llm_call(
            loan_id=loan_id, stage="dim_financial_narrative",
            dimension="financial_docs",
            system=NARRATIVE_PROMPT,
            user="Features:\n```json\n" + _json.dumps(features, default=str) + "\n```",
            json_mode=True,
        )
        return (parsed.get("narrative") or "").strip()[:300]
    except Exception as e:  # noqa: BLE001
        log.warning("financial narrative failed, using template", extra={"err": str(e)})
        aff = features.get("affordability") or {}
        dscr = aff.get("dscr")
        cat = aff.get("dscr_category")
        net = features.get("monthly_net_avg_sar") or 0
        if dscr is not None:
            return f"Monthly net {net:,.0f} SAR, DSCR {dscr:.2f} ({cat})."
        return "Financial analysis based on available documents."


async def run(ctx: dict) -> DimensionOutput:
    loan = ctx["loan"]
    docs = ctx.get("documents") or []
    loan_id = str(loan["id"])

    def _clean(d):
        return d["analysis_report"] if (
            d.get("analysis_status") == "done"
            and d.get("analysis_report")
            and not (d["analysis_report"] or {}).get("error")
        ) else None

    bank_reports = [r for r in (_clean(d) for d in docs if d["doc_type"] == "bank_statement") if r]
    fin_reports = [r for r in (_clean(d) for d in docs if d["doc_type"] == "financial_statement") if r]

    if not bank_reports and not fin_reports:
        return DimensionOutput(
            dimension="financial_docs", score=0, confidence=0.0,
            narrative="No financial documents available.",
            features={}, flags=["no_financial_docs"],
            dimension_version="financial@agg-v1",
        )

    bank_agg = _aggregate_bank_statements(bank_reports)
    fin_agg = _extract_financial_statement(fin_reports)
    reconcile = _reconcile(bank_agg, fin_agg)

    write_event(loan_id=loan_id, stage="dim_financial_reconcile",
                dimension="financial_docs", kind="reconcile", parsed=reconcile)

    amt = float(loan["amount_requested"])
    rate = float(loan.get("profit_rate") or 0.15)
    months = int(loan.get("repayment_months") or 12)
    monthly_net = bank_agg.get("monthly_net_avg_sar")
    if monthly_net is None and fin_agg.get("present"):
        stmt_net = (fin_agg.get("income_statement") or {}).get("net_profit_sar")
        if stmt_net is not None:
            monthly_net = stmt_net / 12
    affordability = _dscr(amt, rate, months, monthly_net)

    dscr = affordability.get("dscr")
    if dscr is None:
        score, confidence = 50.0, 0.5
    elif dscr >= 1.5:
        score, confidence = 80.0, 0.85
    elif dscr >= 1.2:
        score, confidence = 60.0, 0.80
    elif dscr >= 1.0:
        score, confidence = 45.0, 0.75
    else:
        score, confidence = 25.0, 0.75

    flags: list[str] = []
    vol = bank_agg.get("volatility")
    if vol is not None and vol > 0.5:
        score -= 10
        flags.append("high_volatility")
    if bank_agg.get("bounced_count", 0) > 0:
        score -= 5
        flags.append(f"bounced_payments({bank_agg['bounced_count']})")
    if bank_agg.get("overdraft_events", 0) > 0:
        flags.append(f"overdraft_events({bank_agg['overdraft_events']})")
    if reconcile.get("possible") and not reconcile.get("consistent"):
        score -= 10
        flags.append("revenue_reconciliation_failed")
    score = max(0.0, min(100.0, score))

    features = {
        "bank_aggregate": bank_agg,
        "financial_statement": fin_agg,
        "reconciliation": reconcile,
        "monthly_net_avg_sar": monthly_net,
        "monthly_revenue_avg_sar": bank_agg.get("monthly_revenue_avg_sar"),
        "monthly_expenses_avg_sar": bank_agg.get("monthly_expenses_avg_sar"),
        "volatility": bank_agg.get("volatility"),
        "trend": bank_agg.get("trend"),
        "ratios": fin_agg.get("ratios", {}),
        "affordability": affordability,
        "source_document_count": len(bank_reports) + len(fin_reports),
    }

    narrative = await _narrative(loan_id, features)

    return DimensionOutput(
        dimension="financial_docs",
        score=score, confidence=confidence, narrative=narrative,
        features=features, flags=flags,
        dimension_version="financial@agg-v1",
    )

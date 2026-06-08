"""Cashflow comparator.

Computes the platform's current portfolio exposure and compares it against
the historical average from past risk_snapshots. Combines with market status
to produce a final risk_appetite.
"""
from __future__ import annotations

import logging
from typing import Literal

from ..supabase_client import get_client

log = logging.getLogger(__name__)

Appetite = Literal["conservative", "moderate", "aggressive"]


def current_portfolio_exposure() -> dict:
    """Sum approved_amount across active loans. 'Active' = status='approved' and not fully repaid."""
    sb = get_client()
    rows = sb.table("loans").select(
        "id, approved_amount, amount_paid, monthly_payment, status"
    ).eq("status", "approved").execute().data or []

    total_exposure = 0.0
    active_count = 0
    dscr_list: list[float] = []
    for r in rows:
        approved = float(r.get("approved_amount") or 0)
        paid = float(r.get("amount_paid") or 0)
        remaining = max(0.0, approved - paid)
        if remaining > 0:
            total_exposure += remaining
            active_count += 1

    return {
        "total_approved_exposure_sar": round(total_exposure, 2),
        "active_loan_count": active_count,
        "avg_dscr_portfolio": None,  # TODO: compute once DSCR stored on loan
    }


def historical_avg_exposure(window: int = 20) -> float | None:
    """Mean of total_approved_exposure_sar across last N snapshots."""
    sb = get_client()
    rows = sb.table("risk_snapshots").select("raw_data").order("captured_at", desc=True).limit(window).execute().data or []
    if not rows:
        return None
    vals = []
    for r in rows:
        rd = r.get("raw_data") or {}
        v = rd.get("total_approved_exposure_sar")
        if v is not None:
            vals.append(float(v))
    if not vals:
        return None
    return sum(vals) / len(vals)


def cashflow_signal(current_exposure: float, historical_avg: float | None) -> tuple[Appetite, float]:
    """Map exposure ratio → (cashflow_appetite, cashflow_score)."""
    if historical_avg is None or historical_avg == 0:
        return "moderate", 50.0
    ratio = current_exposure / historical_avg
    if ratio < 0.8:
        return "aggressive", 75.0
    if ratio <= 1.10:
        return "moderate", 55.0
    return "conservative", 35.0


# Matrix: (market_status, cashflow_appetite) -> final risk_appetite
MATRIX: dict[tuple[str, Appetite], Appetite] = {
    ("low_risk",    "aggressive"):   "aggressive",
    ("low_risk",    "moderate"):     "aggressive",
    ("low_risk",    "conservative"): "moderate",
    ("medium_risk", "aggressive"):   "moderate",
    ("medium_risk", "moderate"):     "moderate",
    ("medium_risk", "conservative"): "conservative",
    ("high_risk",   "aggressive"):   "conservative",
    ("high_risk",   "moderate"):     "conservative",
    ("high_risk",   "conservative"): "conservative",
}


def combine(market_status: str, cashflow_appetite: Appetite) -> Appetite:
    return MATRIX.get((market_status, cashflow_appetite), "moderate")

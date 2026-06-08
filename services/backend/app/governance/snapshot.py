"""Risk snapshot: combine market + cashflow → risk_appetite, persist."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from ..supabase_client import get_client
from . import cashflow, market

log = logging.getLogger(__name__)


def take_snapshot() -> dict:
    """Compute a fresh snapshot and insert into risk_snapshots."""
    sb = get_client()

    m = market.current()
    exposure = cashflow.current_portfolio_exposure()
    hist_avg = cashflow.historical_avg_exposure()
    appetite, cf_score = cashflow.cashflow_signal(
        exposure["total_approved_exposure_sar"], hist_avg
    )
    final_appetite = cashflow.combine(m["market_status"], appetite)

    # Grab current policy id if one exists
    pol = sb.table("risk_policies").select("id").order("effective_from", desc=True).limit(1).execute().data
    policy_id = pol[0]["id"] if pol else None

    row = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "market_status": m["market_status"],
        "market_notes": m["market_notes"],
        "cashflow_score": cf_score,
        "risk_appetite": final_appetite,
        "raw_data": {
            **exposure,
            "historical_avg_exposure_sar": hist_avg,
            "market": m,
            "cashflow_appetite_raw": appetite,
        },
        "policy_id": policy_id,
    }
    ins = sb.table("risk_snapshots").insert(row).execute()
    saved = ins.data[0] if ins.data else row
    log.info("risk snapshot captured", extra={
        "market_status": m["market_status"],
        "risk_appetite": final_appetite,
        "exposure": exposure["total_approved_exposure_sar"],
    })
    return saved


async def run_scheduler(interval_s: int, stop_event: asyncio.Event) -> None:
    """Periodic background task — runs until stop_event is set."""
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(take_snapshot)
        except Exception as e:  # noqa: BLE001
            log.exception("scheduled snapshot failed", extra={"err": str(e)})
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_s)
        except asyncio.TimeoutError:
            continue

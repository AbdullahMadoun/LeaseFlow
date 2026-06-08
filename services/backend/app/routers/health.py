"""Health check. Lightweight Supabase ping so misconfigured service_key fails fast."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ..analyst_service import healthcheck as analyst_healthcheck
from ..config import CONFIG
from ..supabase_client import get_client

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    db_ok = True
    db_err: str | None = None
    try:
        get_client().table("segments").select("name").limit(1).execute()
    except Exception as e:
        db_ok = False
        db_err = str(e)[:200]

    analyst = await analyst_healthcheck()
    overall_ok = db_ok and (not analyst.get("configured") or analyst.get("reachable"))

    return {
        "status": "ok" if overall_ok else "degraded",
        "ts": datetime.now(timezone.utc).isoformat(),
        "env": CONFIG.env,
        "supabase": {"reachable": db_ok, "error": db_err},
        "analyst": analyst,
        "llm_model": CONFIG.llm_model,
        "decision_mode": CONFIG.decision_mode,
    }

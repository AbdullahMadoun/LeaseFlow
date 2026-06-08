"""Risk governance endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ..governance import snapshot
from ..supabase_client import get_client

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/snapshot")
async def post_snapshot() -> dict:
    row = snapshot.take_snapshot()
    return {"status": "ok", "snapshot": row}


@router.get("/current")
async def get_current() -> dict:
    sb = get_client()
    rows = sb.table("risk_snapshots").select("*").order("captured_at", desc=True).limit(1).execute().data
    return {"snapshot": rows[0] if rows else None}

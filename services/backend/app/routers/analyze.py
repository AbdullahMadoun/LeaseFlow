"""/analyze/* endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import orchestrator
from ..schemas import AnalyzeStartRequest, AnalyzeStartResponse, AnalyzeStatusResponse

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("/start", response_model=AnalyzeStartResponse)
async def analyze_start(body: AnalyzeStartRequest) -> dict:
    try:
        return await orchestrator.start_analysis(str(body.loan_id))
    except orchestrator.RequiredDocumentsMissing as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "required_documents_missing", **e.missing},
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/status/{loan_id}", response_model=AnalyzeStatusResponse)
async def analyze_status(loan_id: str) -> dict:
    try:
        return await orchestrator.get_status(loan_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/trace/{loan_id}")
async def analyze_trace(loan_id: str) -> dict:
    """Full audit trail: every LLM call, rule, aggregation, reconcile, extraction
    for this loan, plus the per-document extraction reports.

    Admin-only. The ai_traces table has RLS allowing only is_admin() readers —
    the backend service_role key bypasses RLS, so this endpoint is effectively
    open via the orchestrator and should be fronted by an admin check in
    whatever edge/proxy sits in front of it, or by admins calling this via
    the Supabase REST API directly with their JWT.
    """
    try:
        return await orchestrator.get_trace(loan_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/analyst/start/{loan_id}")
async def analyst_start(loan_id: str) -> dict:
    try:
        return await orchestrator.start_analyst(loan_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/analyst/status/{loan_id}")
async def analyst_status(loan_id: str) -> dict:
    try:
        return await orchestrator.get_analyst_status(loan_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/analyst/report/{loan_id}")
async def analyst_report(loan_id: str) -> dict:
    try:
        return await orchestrator.get_analyst_report(loan_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

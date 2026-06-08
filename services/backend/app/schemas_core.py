"""Pydantic models — shared shapes for dim outputs, decisions, API bodies."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

DimensionName = Literal["pos", "financial_docs", "simah", "sentiment", "industry"]
DimensionStatus = Literal["queued", "processing", "done", "error", "skipped"]
LoanStatus = Literal["pending_analysis", "analyzing", "manual_review", "approved", "denied"]
DocType = Literal["bank_statement", "pos_data", "financial_statement", "invoice"]


class DimensionOutput(BaseModel):
    """Normalized output from any of the 5 dims."""
    dimension: DimensionName
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    narrative: str
    features: dict[str, Any] = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)
    dimension_version: str = "v1"
    analyst_job_id: str | None = None


class AnalyzeStartRequest(BaseModel):
    loan_id: UUID


class AnalyzeStartResponse(BaseModel):
    status: Literal["started", "already_running", "already_complete"]
    loan_id: UUID
    registered_dimensions: list[DimensionName]


class DimensionStatusRow(BaseModel):
    dimension: DimensionName
    status: DimensionStatus
    score: float | None = None
    confidence: float | None = None
    narrative: str | None = None
    error_message: str | None = None
    updated_at: datetime | None = None


class DocumentStatusRow(BaseModel):
    id: UUID
    doc_type: DocType
    analysis_status: str
    extractor_schema_version: str | None = None


class AnalysisTiming(BaseModel):
    submitted_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    submission_to_decision_s: float | None = None  # submitted_at → completed_at
    pipeline_duration_s: float | None = None       # started_at   → completed_at


class AnalyzeStatusResponse(BaseModel):
    loan_id: UUID
    loan_status: LoanStatus
    synthesis_status: str
    dimensions: list[DimensionStatusRow]
    documents: list[DocumentStatusRow] = Field(default_factory=list)
    timing: AnalysisTiming = Field(default_factory=AnalysisTiming)
    analyst_jobs: dict[str, Any] = Field(default_factory=dict)


class AffordabilityPayload(BaseModel):
    """Deterministic affordability math written to loans.affordability."""
    amount_requested: float
    profit_rate: float
    repayment_months: int
    total_due: float
    proposed_monthly_payment: float
    monthly_net_avg: float | None = None
    dscr: float | None = None
    dscr_category: Literal["comfortable", "marginal", "risky", "unknown"] = "unknown"


class ExpertDecisionPayload(BaseModel):
    """Shape written to loans.decision_payload. Full audit trail."""
    schema_version: str = "v1"
    deterministic_proposal: dict[str, Any]
    hard_floors_check: dict[str, Any]
    llm_response: dict[str, Any] | None
    final_decision: dict[str, Any]
    synthesis_version: str = "expert@v1"
    risk_snapshot_id: str | None = None
    registered_dimensions: list[str]
    dimension_scores: dict[str, float]
    generated_at: str


class LLMDecision(BaseModel):
    """Strict shape the LLM must return in expert synthesis.

    dimension_scores permits `None` per dim because the LLM legitimately can't
    always score a dim (e.g. sentiment falls back to a placeholder when the
    Google place can't be resolved). Null is preserved rather than coerced so
    the UI / audit trail can show "unknown" instead of fabricating a 0.
    """
    decision: Literal["approve", "deny", "manual_review"]
    confidence: float = Field(ge=0, le=1)
    recommended_amount: float | None = None
    reasoning: str
    risk_flags: list[str] = Field(default_factory=list)
    dimension_scores: dict[str, float | None] = Field(default_factory=dict)
    risk_level: Literal["low", "medium", "high"]

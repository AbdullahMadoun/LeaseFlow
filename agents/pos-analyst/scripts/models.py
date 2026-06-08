"""Pydantic models for jobs, plans, findings, state. The on-disk schemas live here."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------- phase + status ----------

Phase = Literal[
    "created", "profile", "context", "plan", "execute", "validate", "report", "done", "failed"
]
JobStatus = Literal["queued", "running", "done", "failed"]
QuestionStatus = Literal["pending", "in_progress", "done", "dropped"]
QuestionPriority = Literal["critical", "high", "normal"]
QuestionSource = Literal["context", "data", "domain", "validation"]
Confidence = Literal["high", "medium", "low"]
TraceKind = Literal[
    "thought", "tool_call", "tool_result", "plan_update", "finding",
    "error", "phase_transition",
]


# ---------- state ----------

class JobState(BaseModel):
    job_id: str
    phase: Phase = "created"
    phase_started_at: str = Field(default_factory=utcnow_iso)
    step_counter: int = 0  # monotonic across the whole job, used as code-step id
    iteration_in_phase: int = 0
    validation_round: int = 0
    status: JobStatus = "queued"
    model_id: str = ""
    created_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)
    error: str | None = None


# ---------- plan ----------

class PlanQuestion(BaseModel):
    id: str
    text: str
    why: str = ""
    expected_signals: str = ""
    source: QuestionSource = "data"
    priority: QuestionPriority = "normal"
    status: QuestionStatus = "pending"
    finding_ids: list[str] = Field(default_factory=list)
    added_in_iteration: int = 0
    completed_in_iteration: int | None = None
    dropped_reason: str | None = None


class Plan(BaseModel):
    version: int = 1
    questions: list[PlanQuestion] = Field(default_factory=list)

    def by_id(self, qid: str) -> PlanQuestion | None:
        return next((q for q in self.questions if q.id == qid), None)

    def critical_pending(self) -> list[PlanQuestion]:
        return [q for q in self.questions if q.priority == "critical" and q.status != "done"]


# ---------- findings ----------

class Finding(BaseModel):
    id: str
    ts: str = Field(default_factory=utcnow_iso)
    iteration: int = 0
    question_id: str
    title: str
    body: str
    numbers: dict[str, Any] = Field(default_factory=dict)
    evidence_step_ids: list[int] = Field(default_factory=list)
    confidence: Confidence = "medium"
    tags: list[str] = Field(default_factory=list)


# ---------- trace ----------

class TraceEntry(BaseModel):
    ts: str = Field(default_factory=utcnow_iso)
    iteration: int = 0
    kind: TraceKind
    content: str = ""
    tool: str | None = None
    step_id: int | None = None
    purpose: str | None = None
    exit_code: int | None = None
    stdout_truncated: bool | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


# ---------- code step metadata ----------

class CodeStepMeta(BaseModel):
    step_id: int
    started_at: str
    ended_at: str
    exit_code: int
    wall_seconds: float
    killed_for_timeout: bool = False
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    purpose: str = ""


class CodeStepRecord(BaseModel):
    step_id: int
    started_at: str
    ended_at: str
    exit_code: int
    wall_seconds: float
    killed_for_timeout: bool = False
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    purpose: str = ""
    code_path: str
    stdout_path: str
    stderr_path: str


# ---------- data profile ----------

class ColumnProfile(BaseModel):
    name: str
    dtype: str
    n_missing: int
    n_unique: int | None = None
    examples: list[str] = Field(default_factory=list)
    min: str | None = None
    max: str | None = None


class FileProfile(BaseModel):
    filename: str
    n_rows: int
    n_cols: int
    columns: list[ColumnProfile]
    n_duplicate_rows: int = 0
    detected_role: dict[str, str] = Field(default_factory=dict)  # canonical_name -> column_name
    quality_flags: list[str] = Field(default_factory=list)
    time_range: dict[str, str] | None = None  # {"column": "...", "min": "...", "max": "..."}
    load_format: str = "csv"


class DataProfile(BaseModel):
    job_id: str
    files: list[FileProfile]
    cross_file_notes: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=utcnow_iso)


# ---------- context summary ----------

class ContextSummary(BaseModel):
    brand: str | None = None
    branches: list[str] = Field(default_factory=list)
    region: str | None = None
    currency: str | None = None
    period_covered: str | None = None
    stated_goals: list[str] = Field(default_factory=list)
    explicit_questions: list[str] = Field(default_factory=list)
    stated_problems: list[str] = Field(default_factory=list)
    implicit_constraints: list[str] = Field(default_factory=list)
    raw_context_present: bool = True


class JobMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    dataset_kind: str | None = None
    currency: str | None = None
    synthetic: bool | None = None
    analysis_time_target_minutes: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "analysis_time_target_minutes",
            "time_budget_target_minutes",
            "target_minutes",
        ),
    )
    analysis_time_hard_cap_minutes: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "analysis_time_hard_cap_minutes",
            "time_budget_hard_cap_minutes",
            "hard_cap_minutes",
        ),
    )
    analysis_time_notes: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "analysis_time_notes",
            "time_budget_notes",
            "time_notes",
        ),
    )


# ---------- validation ----------

class Contradiction(BaseModel):
    finding_a: str
    finding_b: str
    explanation: str
    resolution: str | None = None


class ValidationResult(BaseModel):
    contradictions: list[Contradiction] = Field(default_factory=list)
    hallucinations: list[str] = Field(default_factory=list)  # finding ids
    gaps: list[str] = Field(default_factory=list)
    recommend_more_investigation: list[PlanQuestion] = Field(default_factory=list)


# ---------- API ----------

class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    phase: Phase
    step_counter: int
    iteration_in_phase: int
    error: str | None = None
    created_at: str
    updated_at: str


class JobError(Enum):
    NOT_FOUND = "not_found"
    NOT_READY = "not_ready"
    INVALID = "invalid"

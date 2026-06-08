"""On-disk memory: atomic state writes, append-only JSONL, resume-safe reads.

Every persistence path the worker uses goes through this module so that the
crash-and-resume contract documented in references/memory-schema.md is enforced
in exactly one place.
"""
from __future__ import annotations

import io
import json
import os
import threading
from pathlib import Path
from typing import Any, Iterable, Type, TypeVar

from pydantic import BaseModel

from models import (
    CodeStepMeta, CodeStepRecord, ContextSummary, DataProfile, Finding, JobMeta,
    JobState, Plan, PlanQuestion, TraceEntry, ValidationResult, utcnow_iso,
)

T = TypeVar("T", bound=BaseModel)


# ---------------- low-level fs primitives ----------------

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(path: Path) -> threading.Lock:
    with _LOCKS_GUARD:
        lk = _LOCKS.get(str(path))
        if lk is None:
            lk = threading.Lock()
            _LOCKS[str(path)] = lk
        return lk


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with _lock_for(path):
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        _fsync_dir(path.parent)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with _lock_for(path):
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        _fsync_dir(path.parent)


def atomic_write_model(path: Path, model: BaseModel) -> None:
    atomic_write_text(path, model.model_dump_json(indent=2))


def append_jsonl(path: Path, obj: BaseModel | dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = obj.model_dump_json() if isinstance(obj, BaseModel) else json.dumps(obj, ensure_ascii=False)
    line += "\n"
    with _lock_for(path):
        with open(path, "ab") as f:
            f.write(line.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())


def read_jsonl(path: Path, model: Type[T] | None = None) -> list[Any]:
    """Read JSONL; silently drop the trailing line if it lacks a newline (crashed write)."""
    if not path.exists():
        return []
    with open(path, "rb") as f:
        raw = f.read()
    if not raw:
        return []
    parts = raw.split(b"\n")
    # If file ends with \n, parts[-1] is "". Otherwise it's a partial trailing line we skip.
    parts = parts[:-1]
    out: list[Any] = []
    for line in parts:
        if not line.strip():
            continue
        try:
            obj = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            continue
        out.append(model.model_validate(obj) if model else obj)
    return out


# ---------------- per-job memory facade ----------------

class JobMemory:
    """Thin facade over the per-job directory tree."""

    def __init__(self, job_dir: Path) -> None:
        self.job_dir = job_dir
        self.input_dir = job_dir / "input"
        self.data_dir = self.input_dir / "data"
        self.memory_dir = job_dir / "memory"
        self.code_steps_dir = self.memory_dir / "code_steps"
        self.output_dir = job_dir / "output"
        self.state_path = job_dir / "state.json"
        self.log_path = job_dir / "job.log"
        self.context_path = self.input_dir / "context.md"
        self.meta_path = self.input_dir / "meta.json"
        self.profile_path = self.memory_dir / "data_profile.json"
        self.context_summary_path = self.memory_dir / "context_summary.json"
        self.plan_path = self.memory_dir / "plan.json"
        self.findings_path = self.memory_dir / "findings.jsonl"
        self.trace_path = self.memory_dir / "trace.jsonl"
        self.code_steps_index_path = self.memory_dir / "code_steps.jsonl"
        self.validation_path = self.memory_dir / "validation.json"
        self.report_path = self.memory_dir / "report.md"
        self.evidence_map_path = self.memory_dir / "evidence_map.md"
        self.served_report_path = self.output_dir / "report.md"

    # ---- bootstrap ----
    def initialise(self) -> None:
        for d in (self.input_dir, self.data_dir, self.memory_dir, self.code_steps_dir, self.output_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ---- state ----
    def read_state(self) -> JobState | None:
        if not self.state_path.exists():
            return None
        return JobState.model_validate_json(self.state_path.read_text(encoding="utf-8"))

    def write_state(self, state: JobState) -> None:
        state.updated_at = utcnow_iso()
        atomic_write_model(self.state_path, state)

    # ---- meta ----
    def write_meta(self, meta: JobMeta) -> None:
        atomic_write_text(self.meta_path, meta.model_dump_json(indent=2, exclude_none=True))

    def read_meta(self) -> JobMeta | None:
        if not self.meta_path.exists():
            return None
        raw = self.meta_path.read_text(encoding="utf-8")
        if not raw.strip():
            return None
        try:
            return JobMeta.model_validate_json(raw)
        except ValueError:
            try:
                return JobMeta.model_validate(json.loads(raw))
            except (ValueError, json.JSONDecodeError):
                return None

    # ---- profile ----
    def write_profile(self, profile: DataProfile) -> None:
        atomic_write_model(self.profile_path, profile)

    def read_profile(self) -> DataProfile | None:
        return DataProfile.model_validate_json(self.profile_path.read_text(encoding="utf-8")) \
            if self.profile_path.exists() else None

    # ---- context summary ----
    def write_context_summary(self, c: ContextSummary) -> None:
        atomic_write_model(self.context_summary_path, c)

    def read_context_summary(self) -> ContextSummary | None:
        return ContextSummary.model_validate_json(self.context_summary_path.read_text(encoding="utf-8")) \
            if self.context_summary_path.exists() else None

    # ---- plan ----
    def write_plan(self, plan: Plan) -> None:
        plan.version += 1
        atomic_write_model(self.plan_path, plan)

    def read_plan(self) -> Plan | None:
        return Plan.model_validate_json(self.plan_path.read_text(encoding="utf-8")) \
            if self.plan_path.exists() else None

    # ---- findings ----
    def append_finding(self, f: Finding) -> None:
        existing_ids = {x.id for x in self.read_findings()}
        if f.id in existing_ids:
            return  # dedupe on resume
        append_jsonl(self.findings_path, f)

    def read_findings(self) -> list[Finding]:
        return read_jsonl(self.findings_path, Finding)

    def next_finding_id(self) -> str:
        return f"f_{len(self.read_findings()) + 1:04d}"

    # ---- trace ----
    def append_trace(self, t: TraceEntry) -> None:
        append_jsonl(self.trace_path, t)

    def read_trace(self) -> list[TraceEntry]:
        return read_jsonl(self.trace_path, TraceEntry)

    def tail_trace(self, n: int) -> list[TraceEntry]:
        all_trace = self.read_trace()
        return all_trace[-n:] if n > 0 else all_trace

    # ---- code steps ----
    def code_step_paths(self, step_id: int) -> dict[str, Path]:
        base = self.code_steps_dir / f"step_{step_id:04d}"
        return {
            "code": base.with_suffix(".py"),
            "stdout": Path(str(base) + ".stdout.txt"),
            "stderr": Path(str(base) + ".stderr.txt"),
            "meta": Path(str(base) + ".meta.json"),
        }

    def write_code_step(
        self,
        step_id: int,
        code: str,
        stdout: bytes,
        stderr: bytes,
        meta: CodeStepMeta,
    ) -> None:
        paths = self.code_step_paths(step_id)
        atomic_write_text(paths["code"], code)
        atomic_write_bytes(paths["stdout"], stdout)
        atomic_write_bytes(paths["stderr"], stderr)
        atomic_write_model(paths["meta"], meta)
        append_jsonl(
            self.code_steps_index_path,
            CodeStepRecord(
                step_id=step_id,
                started_at=meta.started_at,
                ended_at=meta.ended_at,
                exit_code=meta.exit_code,
                wall_seconds=meta.wall_seconds,
                killed_for_timeout=meta.killed_for_timeout,
                stdout_bytes=meta.stdout_bytes,
                stderr_bytes=meta.stderr_bytes,
                purpose=meta.purpose,
                code_path=str(paths["code"].relative_to(self.job_dir)),
                stdout_path=str(paths["stdout"].relative_to(self.job_dir)),
                stderr_path=str(paths["stderr"].relative_to(self.job_dir)),
            ),
        )

    def read_code_step_meta(self, step_id: int) -> CodeStepMeta | None:
        p = self.code_step_paths(step_id)["meta"]
        return CodeStepMeta.model_validate_json(p.read_text(encoding="utf-8")) if p.exists() else None

    def read_code_steps(self) -> list[CodeStepRecord]:
        deduped: dict[int, CodeStepRecord] = {}
        for record in read_jsonl(self.code_steps_index_path, CodeStepRecord):
            deduped[record.step_id] = record
        return [deduped[key] for key in sorted(deduped)]

    def read_code_step(self, step_id: int) -> dict[str, Any] | None:
        paths = self.code_step_paths(step_id)
        meta = self.read_code_step_meta(step_id)
        if meta is None:
            return None
        return {
            "meta": meta.model_dump(),
            "code": paths["code"].read_text(encoding="utf-8") if paths["code"].exists() else "",
            "stdout": paths["stdout"].read_text(encoding="utf-8", errors="replace") if paths["stdout"].exists() else "",
            "stderr": paths["stderr"].read_text(encoding="utf-8", errors="replace") if paths["stderr"].exists() else "",
            "paths": {
                "code": str(paths["code"].relative_to(self.job_dir)),
                "stdout": str(paths["stdout"].relative_to(self.job_dir)),
                "stderr": str(paths["stderr"].relative_to(self.job_dir)),
                "meta": str(paths["meta"].relative_to(self.job_dir)),
            },
        }

    # ---- validation ----
    def write_validation(self, v: ValidationResult) -> None:
        atomic_write_model(self.validation_path, v)

    def read_validation(self) -> ValidationResult | None:
        return ValidationResult.model_validate_json(self.validation_path.read_text(encoding="utf-8")) \
            if self.validation_path.exists() else None

    # ---- report ----
    def write_report(self, markdown: str) -> None:
        atomic_write_text(self.report_path, markdown)
        atomic_write_text(self.served_report_path, markdown)

    def read_report(self) -> str | None:
        return self.report_path.read_text(encoding="utf-8") if self.report_path.exists() else None

    def write_evidence_map(self, markdown: str) -> None:
        atomic_write_text(self.evidence_map_path, markdown)

    # ---- context input ----
    def read_context_md(self) -> str:
        return self.context_path.read_text(encoding="utf-8") if self.context_path.exists() else ""

    def list_data_files(self) -> list[Path]:
        if not self.data_dir.exists():
            return []
        return sorted([p for p in self.data_dir.iterdir() if p.is_file()])

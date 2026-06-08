"""FastAPI service: submit jobs, poll status, fetch reports.

A single-process API with a bounded thread pool of workers. Each POST /jobs
creates an on-disk job dir, writes inputs synchronously, then enqueues a
worker.run_one(job_id) into the pool. The pool size is POS_WORKER_CONCURRENCY.
"""
from __future__ import annotations

import logging
import secrets
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

from config import CONFIG, ensure_dirs
from memory import JobMemory
from models import JobCreatedResponse, JobMeta, JobState, JobStatusResponse, utcnow_iso

import worker

log = logging.getLogger("pos.api")
logging.basicConfig(
    level=getattr(logging, CONFIG.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


_executor: ThreadPoolExecutor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    global _executor
    ensure_dirs()
    _executor = ThreadPoolExecutor(
        max_workers=CONFIG.worker_concurrency,
        thread_name_prefix="pos-worker",
    )
    log.info("api startup: workers=%d work_dir=%s model=%s",
             CONFIG.worker_concurrency, CONFIG.work_dir, CONFIG.model_id)
    # Resume in-flight jobs in a single sweep before serving traffic.
    try:
        resumed = worker.resume_all()
        if resumed:
            log.info("resumed %d jobs: %s", len(resumed), resumed)
    except Exception:
        log.exception("resume_all failed (continuing anyway)")
    try:
        yield
    finally:
        if _executor is not None:
            _executor.shutdown(wait=False, cancel_futures=False)
            _executor = None


app = FastAPI(title="POS Financial Analyst", lifespan=lifespan)


# ---------------- auth ----------------

def _check_api_key(provided: str | None) -> None:
    required = CONFIG.api_key_required
    if not required:
        return  # auth disabled
    if not provided or not secrets.compare_digest(provided, required):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


# ---------------- routes ----------------

@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "model": CONFIG.model_id,
        "work_dir": str(CONFIG.work_dir),
        "sandbox_image": CONFIG.sandbox_image,
        "ts": utcnow_iso(),
    }


@app.post("/jobs", response_model=JobCreatedResponse, status_code=202)
async def submit_job(
    context: str | None = Form(default=None, description="Inline business-context markdown"),
    context_file: UploadFile | None = File(default=None, description="Or upload a context.md file"),
    files: list[UploadFile] = File(..., description="One or more POS data files"),
    meta: str | None = Form(default=None, description="Optional JSON string with hints (brand, period, ...)"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> JobCreatedResponse:
    _check_api_key(x_api_key)
    if not files:
        raise HTTPException(status_code=400, detail="at least one data file is required")
    if context is None and context_file is None:
        raise HTTPException(status_code=400, detail="provide either `context` form field or a `context_file`")

    job_id = f"j_{uuid.uuid4().hex[:16]}"
    mem = JobMemory(CONFIG.job_dir(job_id))
    mem.initialise()

    # Persist context.
    if context_file is not None:
        ctx_bytes = await context_file.read()
        mem.context_path.write_bytes(ctx_bytes)
    else:
        mem.context_path.write_text(context or "", encoding="utf-8")

    # Persist meta.
    if meta:
        try:
            parsed_meta = JobMeta.model_validate_json(meta)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid meta JSON: {exc}") from exc
        mem.write_meta(parsed_meta)

    # Persist data files.
    saved_names: list[str] = []
    for up in files:
        safe = _safe_filename(up.filename or "data.bin")
        dest = mem.data_dir / safe
        with dest.open("wb") as out:
            shutil.copyfileobj(up.file, out)
        saved_names.append(safe)

    # Initial state.
    state = JobState(
        job_id=job_id,
        phase="created",
        status="queued",
        model_id=CONFIG.model_id,
    )
    mem.write_state(state)
    log.info("job %s submitted: %d data files", job_id, len(saved_names))

    # Enqueue.
    assert _executor is not None
    _executor.submit(worker.run_one, job_id)

    return JobCreatedResponse(job_id=job_id, status="queued", created_at=state.created_at)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> JobStatusResponse:
    _check_api_key(x_api_key)
    state = _load_state_or_404(job_id)
    return JobStatusResponse(
        job_id=state.job_id, status=state.status, phase=state.phase,
        step_counter=state.step_counter, iteration_in_phase=state.iteration_in_phase,
        error=state.error, created_at=state.created_at, updated_at=state.updated_at,
    )


@app.get("/jobs/{job_id}/report", response_class=PlainTextResponse)
def get_report(job_id: str, x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    _check_api_key(x_api_key)
    state = _load_state_or_404(job_id)
    if state.status != "done":
        raise HTTPException(status_code=409, detail=f"job not done (status={state.status}, phase={state.phase})")
    mem = JobMemory(CONFIG.job_dir(job_id))
    md = mem.read_report()
    if md is None:
        raise HTTPException(status_code=500, detail="report missing on a done job; check job logs")
    return md


@app.get("/jobs/{job_id}/trace")
def get_trace(job_id: str, limit: int = 200,
              x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> JSONResponse:
    _check_api_key(x_api_key)
    _load_state_or_404(job_id)
    mem = JobMemory(CONFIG.job_dir(job_id))
    trace = mem.read_trace()
    return JSONResponse([t.model_dump() for t in trace[-limit:]])


@app.get("/jobs/{job_id}/findings")
def get_findings(job_id: str,
                 x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> JSONResponse:
    _check_api_key(x_api_key)
    _load_state_or_404(job_id)
    mem = JobMemory(CONFIG.job_dir(job_id))
    return JSONResponse([f.model_dump() for f in mem.read_findings()])


@app.get("/jobs/{job_id}/steps")
def get_steps(job_id: str, x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> JSONResponse:
    _check_api_key(x_api_key)
    _load_state_or_404(job_id)
    mem = JobMemory(CONFIG.job_dir(job_id))
    return JSONResponse([record.model_dump() for record in mem.read_code_steps()])


@app.get("/jobs/{job_id}/steps/{step_id}")
def get_step(job_id: str, step_id: int,
             x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> JSONResponse:
    _check_api_key(x_api_key)
    _load_state_or_404(job_id)
    mem = JobMemory(CONFIG.job_dir(job_id))
    step = mem.read_code_step(step_id)
    if step is None:
        raise HTTPException(status_code=404, detail=f"unknown step_id {step_id} for job {job_id}")
    return JSONResponse(step)


# ---------------- helpers ----------------

def _load_state_or_404(job_id: str) -> JobState:
    if not CONFIG.job_dir(job_id).exists():
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
    mem = JobMemory(CONFIG.job_dir(job_id))
    state = mem.read_state()
    if state is None:
        raise HTTPException(status_code=500, detail="job exists but has no state")
    return state


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = "".join(c for c in base if c.isalnum() or c in "._-")
    return cleaned or "data.bin"

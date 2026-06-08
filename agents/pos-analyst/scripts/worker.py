"""Job worker — phase state machine. Owns advancement, resume, and failure.

Two entry points:
  - run_one(job_id) — drive a single job to completion (used by API on submit)
  - resume_all() — on container start, sweep workdir for jobs in non-terminal
    phases and re-enter them
"""
from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path

from analyst_agent import AgentDeps, AnalystAgent, make_client
from code_sandbox import CodeSandbox
from config import CONFIG
from data_profiler import profile_job
from memory import JobMemory
from models import JobState, TraceEntry, ValidationResult, utcnow_iso
from report_generator import generate_report

log = logging.getLogger("pos.worker")


# --- public ---------------------------------------------------------------

def run_one(job_id: str) -> None:
    job_dir = CONFIG.job_dir(job_id)
    if not job_dir.exists():
        raise FileNotFoundError(f"job dir not found: {job_dir}")
    mem = JobMemory(job_dir)
    mem.initialise()
    state = mem.read_state() or JobState(
        job_id=job_id, phase="created", status="queued", model_id=CONFIG.model_id,
    )
    try:
        _drive(state, mem)
    except Exception as e:
        log.exception("job %s failed", job_id)
        state.status = "failed"
        state.phase = "failed"
        state.error = f"{type(e).__name__}: {e}"
        mem.write_state(state)
        mem.append_trace(TraceEntry(
            kind="error",
            content=f"unhandled: {state.error}\n{traceback.format_exc()[:4000]}",
        ))


def resume_all() -> list[str]:
    if not CONFIG.jobs_dir.exists():
        return []
    resumed: list[str] = []
    for job_dir in sorted(CONFIG.jobs_dir.iterdir()):
        if not job_dir.is_dir():
            continue
        mem = JobMemory(job_dir)
        state = mem.read_state()
        if state is None:
            continue
        if state.phase in {"done", "failed"}:
            continue
        log.info("resuming job %s in phase %s", state.job_id, state.phase)
        run_one(state.job_id)
        resumed.append(state.job_id)
    return resumed


# --- internals ------------------------------------------------------------

def _drive(state: JobState, mem: JobMemory) -> None:
    """Phase advancer. Each phase is idempotent at its boundary."""
    state.status = "running"
    mem.write_state(state)

    # Phase 1: profile (deterministic)
    if state.phase in {"created", "profile"}:
        _enter_phase(state, mem, "profile")
        files = mem.list_data_files()
        if not files:
            raise RuntimeError("no input data files in input/data/")
        profile = profile_job(state.job_id, files)
        mem.write_profile(profile)
        mem.append_trace(TraceEntry(kind="phase_transition", content="profile complete"))

    # Phases 2-6 require an LLM client and (for execute) a sandbox.
    client = make_client()
    sandbox = CodeSandbox(mem)
    sandbox.preflight()
    deps = AgentDeps(mem=mem, sandbox=sandbox, client=client)
    agent = AnalystAgent(deps)

    # Phase 2: read context
    if state.phase in {"profile", "context"}:
        _enter_phase(state, mem, "context")
        agent.run_context_phase(state)

    # Phase 3: plan
    if state.phase in {"context", "plan"}:
        _enter_phase(state, mem, "plan")
        agent.run_plan_phase(state)

    # Phases 4 & 5: execute -> validate -> (maybe execute again) -> ...
    if state.phase in {"plan", "execute", "validate"}:
        _execute_validate_loop(state, mem, agent)

    # Phase 6: report
    if state.phase in {"validate", "report"}:
        _enter_phase(state, mem, "report")
        generate_report(client, mem)

    state.phase = "done"
    state.status = "done"
    mem.write_state(state)
    mem.append_trace(TraceEntry(kind="phase_transition", content="job complete"))


def _execute_validate_loop(state: JobState, mem: JobMemory, agent: AnalystAgent) -> None:
    while True:
        if _hard_runtime_cap_reached(state, mem):
            _force_report_due_to_time_cap(state, mem, "before execute")
            return
        # Execute
        if state.phase != "execute":
            _enter_phase(state, mem, "execute")
        # Within-phase iteration counter is preserved across resumes, so the
        # remaining-iteration budget shrinks as expected after a crash.
        max_iters = max(1, _execute_iter_budget(state))
        agent.run_execute_phase(state, max_iters)

        if _hard_runtime_cap_reached(state, mem):
            _force_report_due_to_time_cap(state, mem, "after execute")
            return

        # Validate
        _enter_phase(state, mem, "validate")
        result = agent.run_validate_phase(state)

        # Decide whether to loop
        if not result.recommend_more_investigation:
            return
        if state.validation_round + 1 >= CONFIG.max_validation_rounds:
            mem.append_trace(TraceEntry(
                kind="error",
                content=f"validation suggested {len(result.recommend_more_investigation)} more questions, "
                        f"but max validation rounds ({CONFIG.max_validation_rounds}) reached",
            ))
            return
        # Push new questions onto the plan and re-enter execute
        plan = mem.read_plan()
        if plan is not None:
            for q in result.recommend_more_investigation:
                # Avoid id collisions if model returns ids that happen to match.
                if plan.by_id(q.id):
                    q.id = f"{q.id}_{len(plan.questions) + 1}"
                plan.questions.append(q)
            mem.write_plan(plan)
        state.validation_round += 1
        mem.append_trace(TraceEntry(
            kind="phase_transition",
            content=f"re-entering execute for validation round {state.validation_round}",
        ))


def _execute_iter_budget(state: JobState) -> int:
    """How many more LLM turns the execute phase may consume.

    The hard cap is the code-step budget; iteration count tracks turns rather
    than steps because a turn may include zero or many step calls. We size the
    soft iteration cap as 2x the remaining step budget — enough headroom for
    refinement turns without unbounded looping.
    """
    return max(8, 2 * (CONFIG.max_code_steps - state.step_counter))


def _hard_runtime_cap_reached(state: JobState, mem: JobMemory) -> bool:
    meta = mem.read_meta()
    hard_cap_minutes = meta.analysis_time_hard_cap_minutes if meta else None
    hard_cap_minutes = hard_cap_minutes if hard_cap_minutes and hard_cap_minutes > 0 else CONFIG.default_hard_cap_minutes
    if hard_cap_minutes <= 0:
        return False
    created_at = datetime.fromisoformat(state.created_at.replace("Z", "+00:00"))
    elapsed_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
    return elapsed_seconds >= hard_cap_minutes * 60


def _force_report_due_to_time_cap(state: JobState, mem: JobMemory, location: str) -> None:
    _enter_phase(state, mem, "validate")
    if mem.read_validation() is None:
        mem.write_validation(ValidationResult())
    mem.append_trace(TraceEntry(
        kind="error",
        content=f"job runtime hard cap reached {location}; skipping further investigation and moving to report",
    ))


def _enter_phase(state: JobState, mem: JobMemory, phase: str) -> None:
    if state.phase == phase:
        return
    state.phase = phase  # type: ignore[assignment]
    state.phase_started_at = utcnow_iso()
    state.iteration_in_phase = 0
    mem.write_state(state)
    mem.append_trace(TraceEntry(kind="phase_transition", content=f"entering phase: {phase}"))

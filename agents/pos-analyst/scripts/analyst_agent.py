"""The analyst agent — phase orchestration + tool-use loop.

The worker calls AnalystAgent.run_phase(...) for each phase. Within the execute
phase, the agent loops over LLM turns, dispatching tool calls until either
finish_analysis is called or the step budget is exhausted.

Crash-safety: every tool call commits to disk before the next LLM round-trip,
so a kill at any point loses at most the in-flight LLM call (which we just
re-issue on resume).
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError, APIStatusError

from config import CONFIG
from code_sandbox import CodeSandbox, SandboxResult
from external_knowledge import search as web_search_call
from memory import JobMemory
from models import (
    ContextSummary, Finding, JobState, Plan, PlanQuestion,
    TraceEntry, ValidationResult, utcnow_iso,
)
from prompts import (
    SYSTEM_PROMPT, TOOLS,
    CONTEXT_PHASE_INSTRUCTION, PLAN_PHASE_INSTRUCTION,
    VALIDATE_PHASE_INSTRUCTION,
)

log = logging.getLogger("pos.agent")


# ---------------- LLM client ----------------

def make_client() -> OpenAI:
    if not CONFIG.api_key:
        raise RuntimeError("MINIMAX_API_KEY is not set")
    return OpenAI(api_key=CONFIG.api_key, base_url=CONFIG.api_base, timeout=CONFIG.request_timeout_s)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (APIConnectionError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in {408, 409, 429, 500, 502, 503, 504}
    return False


def llm_call(client: OpenAI, **kwargs: Any) -> Any:
    """OpenAI-compatible call with bounded exponential backoff."""
    delay = 1.5
    last: Exception | None = None
    for attempt in range(CONFIG.max_retries):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001 — propagate non-retryables below
            last = e
            if not _is_retryable(e) or attempt == CONFIG.max_retries - 1:
                raise
            sleep = delay * (2 ** attempt)
            log.warning("llm retry %d/%d after %.1fs: %s", attempt + 1, CONFIG.max_retries, sleep, e)
            time.sleep(sleep)
    assert last is not None
    raise last


# ---------------- helpers ----------------

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def extract_json_object(text: str) -> dict:
    """Best-effort: find the first JSON object in `text`, tolerate code fences and stray prose."""
    s = text.strip()
    # Most likely path: model returned exactly the JSON.
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    m = _JSON_BLOCK_RE.search(s)
    if m:
        return json.loads(m.group(1))
    # Fallback: grab from the first '{' to the matching last '}' by brace counting.
    start = s.find("{")
    if start < 0:
        raise ValueError("no JSON object found in model output")
    depth = 0
    for i in range(start, len(s)):
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(s[start:i + 1])
    raise ValueError("unbalanced braces in model output")


def _normalise_priority(value: Any, default: str = "normal") -> str:
    raw = str(value or default).strip().lower()
    aliases = {
        "med": "high",
        "medium": "high",
        "low": "normal",
        "urgent": "critical",
    }
    raw = aliases.get(raw, raw)
    return raw if raw in {"critical", "high", "normal"} else default


def _normalise_source(value: Any, default: str = "data") -> str:
    raw = str(value or default).strip().lower()
    return raw if raw in {"context", "data", "domain", "validation"} else default


# ---------------- the agent ----------------

@dataclass
class AgentDeps:
    mem: JobMemory
    sandbox: CodeSandbox
    client: OpenAI


@dataclass(frozen=True)
class RuntimeBudget:
    elapsed_seconds: float
    target_minutes: int | None
    hard_cap_minutes: int | None
    target_remaining_seconds: int | None
    hard_cap_remaining_seconds: int | None
    note: str = ""

    @property
    def elapsed_minutes(self) -> float:
        return self.elapsed_seconds / 60.0

    @property
    def over_target(self) -> bool:
        return self.target_remaining_seconds is not None and self.target_remaining_seconds <= 0

    @property
    def hard_cap_reached(self) -> bool:
        return self.hard_cap_remaining_seconds is not None and self.hard_cap_remaining_seconds <= 0


class AnalystAgent:
    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps
        self.mem = deps.mem
        self.sandbox = deps.sandbox
        self.client = deps.client

    # =================== Phase 2: read context ===================
    def run_context_phase(self, state: JobState) -> ContextSummary:
        profile = self.mem.read_profile()
        from data_profiler import render_profile_for_prompt
        ctx_md = self.mem.read_context_md() or "(no context document was provided)"

        user_msg = (
            f"{CONTEXT_PHASE_INSTRUCTION}\n\n"
            f"---- CONTEXT DOCUMENT ----\n{ctx_md}\n\n"
            f"---- DATA PROFILE ----\n{render_profile_for_prompt(profile, max_chars=4000)}\n"
        )
        resp = llm_call(
            self.client,
            model=CONFIG.model_id,
            temperature=CONFIG.temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        text = resp.choices[0].message.content or "{}"
        try:
            obj = extract_json_object(text)
        except ValueError:
            obj = {}
        obj.setdefault("raw_context_present", bool(self.mem.read_context_md().strip()))
        summary = ContextSummary.model_validate(obj)
        self.mem.write_context_summary(summary)
        self.mem.append_trace(TraceEntry(
            iteration=0, kind="phase_transition",
            content="context summary committed",
        ))
        return summary

    # =================== Phase 3: plan ===================
    def run_plan_phase(self, state: JobState) -> Plan:
        profile = self.mem.read_profile()
        ctx = self.mem.read_context_summary()
        from data_profiler import render_profile_for_prompt
        user_msg = (
            f"{PLAN_PHASE_INSTRUCTION}\n\n"
            f"---- CONTEXT SUMMARY ----\n{ctx.model_dump_json(indent=2) if ctx else '{}'}\n\n"
            f"---- DATA PROFILE ----\n{render_profile_for_prompt(profile, max_chars=4500)}\n"
        )
        resp = llm_call(
            self.client,
            model=CONFIG.model_id,
            temperature=CONFIG.temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        text = resp.choices[0].message.content or "{}"
        try:
            obj = extract_json_object(text)
        except ValueError:
            obj = {"questions": []}
        questions: list[PlanQuestion] = []
        for i, q in enumerate(obj.get("questions") or [], start=1):
            questions.append(PlanQuestion(
                id=f"q{i}",
                text=q.get("text", ""),
                why=q.get("why", ""),
                expected_signals=q.get("expected_signals", ""),
                source=_normalise_source(q.get("source"), "data"),
                priority=_normalise_priority(q.get("priority"), "normal"),
            ))
        plan = Plan(version=0, questions=questions)
        self._enforce_plan_completeness(plan, ctx)
        self.mem.write_plan(plan)
        self.mem.append_trace(TraceEntry(
            iteration=0, kind="phase_transition",
            content=f"plan committed with {len(plan.questions)} questions",
        ))
        return plan

    def _enforce_plan_completeness(self, plan: Plan, ctx: ContextSummary | None) -> None:
        """Make sure context-stated questions and problems are critical entries.
        If the model missed any, append them — better to have a near-duplicate
        than to silently drop an owner's question."""
        if ctx is None:
            return
        existing_texts = [q.text.strip().lower() for q in plan.questions]

        def _present(needle: str) -> bool:
            n = needle.strip().lower()
            return any(n in t or t in n for t in existing_texts) if n else True

        next_id = lambda: f"q{len(plan.questions) + 1}"  # noqa: E731

        for eq in ctx.explicit_questions:
            if not _present(eq):
                plan.questions.append(PlanQuestion(
                    id=next_id(), text=eq.strip(),
                    why="Owner explicitly raised this in the brief.",
                    source="context", priority="critical",
                ))
        for sp in ctx.stated_problems:
            phrased = f"Does the data support the claim that {sp.strip().rstrip('.')}?"
            if not _present(phrased):
                plan.questions.append(PlanQuestion(
                    id=next_id(), text=phrased,
                    why="Owner stated this as a known problem; we must verify.",
                    source="context", priority="critical",
                ))

    # =================== Phase 4: execute (the loop) ===================
    def run_execute_phase(self, state: JobState, max_iterations: int) -> JobState:
        plan = self.mem.read_plan()
        assert plan is not None, "execute phase requires a plan"

        messages = self._build_execute_seed_messages(state)
        consecutive_no_call = 0

        while state.iteration_in_phase < max_iterations:
            budget = self._runtime_budget(state)
            if budget.hard_cap_reached:
                self.mem.append_trace(TraceEntry(
                    iteration=state.iteration_in_phase, kind="error",
                    content=(
                        f"job runtime hard cap reached at {budget.elapsed_minutes:.1f}m; "
                        "forcing transition to validation"
                    ),
                ))
                return state
            state.iteration_in_phase += 1
            self.mem.append_trace(TraceEntry(
                iteration=state.iteration_in_phase, kind="thought",
                content=f"execute turn {state.iteration_in_phase} (steps used: {state.step_counter})",
            ))

            # Per-turn dynamic context (NOT cached): plan + recent findings + recent trace + current question.
            messages = self._refresh_dynamic_context(messages, state)

            resp = llm_call(
                self.client,
                model=CONFIG.model_id,
                temperature=CONFIG.temperature,
                tools=TOOLS,
                messages=messages,
            )
            choice = resp.choices[0]
            msg = choice.message

            # Append the model's full assistant message — required by the
            # MiniMax multi-turn tool-use contract — including tool_calls.
            asst_dict: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            if getattr(msg, "tool_calls", None):
                asst_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(asst_dict)

            tool_calls = getattr(msg, "tool_calls", None) or []
            if not tool_calls:
                consecutive_no_call += 1
                self.mem.append_trace(TraceEntry(
                    iteration=state.iteration_in_phase, kind="error",
                    content=f"model returned no tool call (text len={len(msg.content or '')}); nudging",
                ))
                # Nudge once; if the model still doesn't act after two empties, force-finish.
                if consecutive_no_call >= 2:
                    self.mem.append_trace(TraceEntry(
                        iteration=state.iteration_in_phase, kind="error",
                        content="two consecutive empty turns; transitioning to validation",
                    ))
                    break
                messages.append({
                    "role": "user",
                    "content": "You must use a tool every turn. Pick the next pending plan question and call run_python, or call finish_analysis with a reason if everything critical is done.",
                })
                continue
            consecutive_no_call = 0

            # Execute every tool the model called this turn.
            done_signal = False
            for tc in tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                tool_result = self._dispatch_tool(state, tool_name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": tool_result,
                })
                if tool_name == "finish_analysis":
                    if self._can_finish():
                        done_signal = True
                    # else: _dispatch_tool already wrote a refusal into tool_result

            self.mem.write_state(state)

            if done_signal:
                self.mem.append_trace(TraceEntry(
                    iteration=state.iteration_in_phase, kind="phase_transition",
                    content="finish_analysis accepted; ending execute phase",
                ))
                return state

            if state.step_counter >= CONFIG.max_code_steps:
                self.mem.append_trace(TraceEntry(
                    iteration=state.iteration_in_phase, kind="error",
                    content=f"step budget exhausted ({state.step_counter}); forcing transition to validation",
                ))
                return state

        return state

    def _build_execute_seed_messages(self, state: JobState) -> list[dict[str, Any]]:
        """Build the (large, cacheable) opening messages for the execute loop."""
        from data_profiler import render_profile_for_prompt
        profile = self.mem.read_profile()
        ctx = self.mem.read_context_summary()
        budget = self._runtime_budget(state)
        seed = (
            "PHASE: execute\n\n"
            "You are now in the analysis loop. Read the plan, pick the next pending "
            "question (critical first), and make progress with one tool call per turn. "
            "Keep going until everything critical is answered, then call finish_analysis.\n\n"
            "---- TIME BUDGET ----\n"
            f"{self._render_runtime_budget(budget)}\n\n"
            f"---- DATA PROFILE ----\n{render_profile_for_prompt(profile, max_chars=4500)}\n\n"
            f"---- CONTEXT SUMMARY ----\n{ctx.model_dump_json(indent=2) if ctx else '{}'}\n"
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": seed},
        ]

    def _refresh_dynamic_context(self, messages: list[dict[str, Any]], state: JobState) -> list[dict[str, Any]]:
        """Drop any prior dynamic-context message and add the current one."""
        plan = self.mem.read_plan()
        findings = self.mem.read_findings()[-CONFIG.findings_window:]
        trace = self.mem.tail_trace(CONFIG.trace_window)
        next_q = next((q for q in (plan.questions if plan else []) if q.status == "pending"), None)
        critical_remaining = len((plan.critical_pending() if plan else []))
        budget = self._runtime_budget(state)

        # Compact rendering. Keep it short — the LLM has the full disk via run_python anyway.
        plan_json = plan.model_dump_json(indent=2) if plan else "{}"
        if len(plan_json) > 6000:
            plan_json = plan_json[:6000] + "\n... [plan truncated; see /scratch/plan.json if needed]"
        findings_compact = "\n".join(
            f"- {f.id} [{f.confidence}] q={f.question_id} :: {f.title}" for f in findings
        ) or "(no findings yet)"
        trace_compact = "\n".join(
            f"- {t.kind}{f' tool={t.tool}' if t.tool else ''}{f' step={t.step_id}' if t.step_id is not None else ''} :: {t.content[:200]}"
            for t in trace
        ) or "(no trace yet)"

        dynamic = (
            "---- DYNAMIC CONTEXT (this turn) ----\n"
            f"TIME BUDGET:\n{self._render_runtime_budget(budget)}\n"
            f"Time posture: {self._runtime_guidance(budget, critical_remaining)}\n"
            "Internal memory note: do not spend `run_python` steps reading `plan.json`, "
            "`trace.jsonl`, or similar memory files already summarized here unless you are diagnosing corruption.\n"
            f"Critical questions remaining: {critical_remaining}\n"
            f"Next pending question: {next_q.id if next_q else 'none'} — {next_q.text if next_q else ''}\n\n"
            f"PLAN:\n{plan_json}\n\n"
            f"RECENT FINDINGS (most recent {len(findings)}):\n{findings_compact}\n\n"
            f"RECENT TRACE (most recent {len(trace)}):\n{trace_compact}\n"
        )

        # Replace any prior "DYNAMIC CONTEXT" user message — keep history small.
        cleaned: list[dict[str, Any]] = []
        for m in messages:
            if m.get("role") == "user" and isinstance(m.get("content"), str) \
                    and m["content"].startswith("---- DYNAMIC CONTEXT"):
                continue
            cleaned.append(m)
        cleaned.append({"role": "user", "content": dynamic})
        return cleaned

    def _runtime_budget(self, state: JobState) -> RuntimeBudget:
        meta = self.mem.read_meta()
        target_minutes = meta.analysis_time_target_minutes if meta else None
        hard_cap_minutes = meta.analysis_time_hard_cap_minutes if meta else None
        note = (meta.analysis_time_notes or "").strip() if meta else ""

        target_minutes = target_minutes if target_minutes and target_minutes > 0 else CONFIG.default_target_minutes
        hard_cap_minutes = hard_cap_minutes if hard_cap_minutes and hard_cap_minutes > 0 else CONFIG.default_hard_cap_minutes
        if target_minutes <= 0:
            target_minutes = None
        if hard_cap_minutes <= 0:
            hard_cap_minutes = None
        if target_minutes and hard_cap_minutes and target_minutes > hard_cap_minutes:
            target_minutes = hard_cap_minutes

        created_at = datetime.fromisoformat(state.created_at.replace("Z", "+00:00"))
        elapsed_seconds = max(0.0, (datetime.now(timezone.utc) - created_at).total_seconds())
        target_remaining = int(target_minutes * 60 - elapsed_seconds) if target_minutes else None
        hard_cap_remaining = int(hard_cap_minutes * 60 - elapsed_seconds) if hard_cap_minutes else None
        return RuntimeBudget(
            elapsed_seconds=elapsed_seconds,
            target_minutes=target_minutes,
            hard_cap_minutes=hard_cap_minutes,
            target_remaining_seconds=target_remaining,
            hard_cap_remaining_seconds=hard_cap_remaining,
            note=note,
        )

    def _render_runtime_budget(self, budget: RuntimeBudget) -> str:
        lines = [f"- Elapsed runtime: {budget.elapsed_minutes:.1f} minutes"]
        if budget.target_minutes is None:
            lines.append("- Target runtime: none")
        else:
            lines.append(f"- Target runtime: {budget.target_minutes} minutes")
            lines.append(
                f"- Remaining until target: {self._format_remaining_seconds(budget.target_remaining_seconds)}"
            )
        if budget.hard_cap_minutes is None:
            lines.append("- Hard cap runtime: none")
        else:
            lines.append(f"- Hard cap runtime: {budget.hard_cap_minutes} minutes")
            lines.append(
                f"- Remaining until hard cap: {self._format_remaining_seconds(budget.hard_cap_remaining_seconds)}"
            )
        if budget.note:
            lines.append(f"- Time note: {budget.note}")
        return "\n".join(lines)

    def _runtime_guidance(self, budget: RuntimeBudget, critical_remaining: int) -> str:
        if budget.hard_cap_reached:
            return "Hard cap reached. Do not start new work; move straight to the best supported synthesis."
        if budget.over_target:
            if critical_remaining > 0:
                return (
                    "Target runtime exceeded. Stop low-value exploration, combine related questions, "
                    "answer only the remaining critical items, then finish."
                )
            return "Target runtime exceeded and no critical questions remain. Stop investigating and finish now."
        if budget.target_remaining_seconds is not None and budget.target_remaining_seconds <= 120:
            return "Target runtime is imminent. Avoid detours and use each step only to close a critical question."
        if budget.target_remaining_seconds is not None and budget.target_remaining_seconds <= 300:
            return "Target runtime is close. Prefer high-yield analyses that close multiple critical questions at once."
        return "Within budget. Work deliberately and avoid spending steps on internal memory files already summarized."

    @staticmethod
    def _format_remaining_seconds(value: int | None) -> str:
        if value is None:
            return "n/a"
        if value <= 0:
            return "0m (budget exceeded)"
        minutes, seconds = divmod(value, 60)
        return f"{minutes}m {seconds}s"

    # ---- tool dispatch ----
    def _dispatch_tool(self, state: JobState, name: str, args: dict[str, Any]) -> str:
        if name == "run_python":
            return self._tool_run_python(state, args)
        if name == "record_finding":
            return self._tool_record_finding(state, args)
        if name == "update_plan":
            return self._tool_update_plan(state, args)
        if name == "web_search":
            return self._tool_web_search(state, args)
        if name == "finish_analysis":
            return self._tool_finish_analysis(state, args)
        return json.dumps({"error": f"unknown tool: {name}"})

    def _tool_run_python(self, state: JobState, args: dict[str, Any]) -> str:
        code = str(args.get("code", "")).strip()
        purpose = str(args.get("purpose", "")).strip() or "(unspecified)"
        if not code:
            return json.dumps({"error": "empty code"})
        if state.step_counter >= CONFIG.max_code_steps:
            return json.dumps({"error": "step budget exhausted; call finish_analysis"})
        state.step_counter += 1
        step_id = state.step_counter
        self.mem.append_trace(TraceEntry(
            iteration=state.iteration_in_phase, kind="tool_call",
            tool="run_python", step_id=step_id, purpose=purpose, content=purpose,
        ))
        result: SandboxResult = self.sandbox.run(step_id, code, purpose)
        head_kb = CONFIG.sandbox_output_head_kb
        tail_kb = CONFIG.sandbox_output_tail_kb
        stdout_view, stderr_view = result.head_tail(head_kb, tail_kb)
        self.mem.append_trace(TraceEntry(
            iteration=state.iteration_in_phase, kind="tool_result",
            step_id=step_id, exit_code=result.exit_code,
            stdout_truncated=result.stdout_truncated,
            stdout_path=str(self.mem.code_step_paths(step_id)["stdout"]),
            stderr_path=str(self.mem.code_step_paths(step_id)["stderr"]),
            content=f"exit={result.exit_code} wall={result.wall_seconds}s killed={result.killed_for_timeout}",
        ))
        return json.dumps({
            "step_id": step_id,
            "exit_code": result.exit_code,
            "wall_seconds": result.wall_seconds,
            "killed_for_timeout": result.killed_for_timeout,
            "stdout": stdout_view,
            "stderr": stderr_view,
        }, ensure_ascii=False)

    def _tool_record_finding(self, state: JobState, args: dict[str, Any]) -> str:
        qid = str(args.get("question_id", "")).strip()
        title = str(args.get("title", "")).strip()
        body = str(args.get("body", "")).strip()
        steps = [int(s) for s in (args.get("evidence_step_ids") or []) if isinstance(s, (int, float))]
        if not qid or not title or not body or not steps:
            return json.dumps({"error": "question_id, title, body, evidence_step_ids are required"})
        # Validate step ids exist on disk.
        for sid in steps:
            if not self.mem.read_code_step_meta(sid):
                return json.dumps({"error": f"evidence step {sid} not found; cite a real run_python step_id"})
        # Validate question exists.
        plan = self.mem.read_plan()
        q = plan.by_id(qid) if plan else None
        if q is None:
            return json.dumps({"error": f"unknown question_id {qid}"})
        finding = Finding(
            id=self.mem.next_finding_id(),
            iteration=state.iteration_in_phase,
            question_id=qid,
            title=title,
            body=body,
            numbers=args.get("numbers") or {},
            evidence_step_ids=steps,
            confidence=args.get("confidence") or "medium",
            tags=args.get("tags") or [],
        )
        self.mem.append_finding(finding)
        if finding.id not in q.finding_ids:
            q.finding_ids.append(finding.id)
            self.mem.write_plan(plan)
        self.mem.append_trace(TraceEntry(
            iteration=state.iteration_in_phase, kind="finding",
            content=f"{finding.id} :: {finding.title}",
        ))
        return json.dumps({"finding_id": finding.id})

    def _tool_update_plan(self, state: JobState, args: dict[str, Any]) -> str:
        plan = self.mem.read_plan()
        if plan is None:
            return json.dumps({"error": "no plan"})
        changed = False
        for qid in (args.get("mark_done") or []):
            q = plan.by_id(str(qid))
            if q and q.status != "done":
                q.status = "done"
                q.completed_in_iteration = state.iteration_in_phase
                changed = True
        for d in (args.get("drop") or []):
            q = plan.by_id(str(d.get("id")))
            if q and q.status != "dropped":
                q.status = "dropped"
                q.dropped_reason = str(d.get("reason", ""))
                changed = True
        for a in (args.get("add") or []):
            new_id = f"q{len(plan.questions) + 1}"
            plan.questions.append(PlanQuestion(
                id=new_id,
                text=str(a.get("text", "")),
                why=str(a.get("why", "")),
                expected_signals=str(a.get("expected_signals", "")),
                source="data",
                priority=_normalise_priority(a.get("priority"), "normal"),
                added_in_iteration=state.iteration_in_phase,
            ))
            changed = True
        if changed:
            self.mem.write_plan(plan)
            self.mem.append_trace(TraceEntry(
                iteration=state.iteration_in_phase, kind="plan_update",
                content=f"plan now has {len(plan.questions)} questions, "
                        f"{sum(1 for q in plan.questions if q.status == 'done')} done",
            ))
        return json.dumps({"ok": True, "questions": len(plan.questions)})

    def _tool_web_search(self, state: JobState, args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return json.dumps({"error": "empty query"})
        # Per-job budget: count prior web_search calls.
        prior = sum(1 for t in self.mem.read_trace() if t.tool == "web_search")
        if prior >= CONFIG.web_search_max_per_job:
            return json.dumps({"error": "web_search budget exhausted for this job"})
        self.mem.append_trace(TraceEntry(
            iteration=state.iteration_in_phase, kind="tool_call",
            tool="web_search", content=query,
        ))
        res = web_search_call(query, max_results=5)
        self.mem.append_trace(TraceEntry(
            iteration=state.iteration_in_phase, kind="tool_result",
            content=f"web_search returned {len(res.hits)} hits (err={res.error})",
        ))
        return res.to_prompt()

    def _tool_finish_analysis(self, state: JobState, args: dict[str, Any]) -> str:
        if self._can_finish():
            return json.dumps({"accepted": True, "reason": str(args.get("reason", ""))})
        plan = self.mem.read_plan()
        remaining = [q.id for q in (plan.critical_pending() if plan else [])]
        return json.dumps({
            "accepted": False,
            "error": "critical questions still pending; address them before finishing",
            "remaining_critical": remaining,
        })

    def _can_finish(self) -> bool:
        plan = self.mem.read_plan()
        return plan is not None and len(plan.critical_pending()) == 0

    # =================== Phase 5: validate ===================
    def run_validate_phase(self, state: JobState) -> ValidationResult:
        plan = self.mem.read_plan()
        findings = self.mem.read_findings()
        profile = self.mem.read_profile()

        compact_findings = [
            {
                "id": f.id, "question_id": f.question_id, "title": f.title,
                "numbers": f.numbers, "evidence_step_ids": f.evidence_step_ids,
                "body": f.body[:600],
            }
            for f in findings
        ]

        user_msg = (
            f"{VALIDATE_PHASE_INSTRUCTION}\n\n"
            f"---- PLAN ----\n{plan.model_dump_json(indent=2) if plan else '{}'}\n\n"
            f"---- FINDINGS ----\n{json.dumps(compact_findings, indent=2, ensure_ascii=False)[:30000]}\n\n"
            f"---- DATA PROFILE (compact) ----\n"
            f"files: {[fp.filename for fp in profile.files] if profile else []}\n"
        )
        resp = llm_call(
            self.client,
            model=CONFIG.model_id,
            temperature=0.0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        text = resp.choices[0].message.content or "{}"
        try:
            obj = extract_json_object(text)
        except ValueError:
            obj = {}
        # Hand-roll PlanQuestion construction from the loose schema the prompt asks for.
        new_questions: list[PlanQuestion] = []
        for i, q in enumerate(obj.get("recommend_more_investigation") or [], start=1):
            new_questions.append(PlanQuestion(
                id=f"qv_{state.validation_round + 1}_{i}",
                text=str(q.get("text", "")),
                why=str(q.get("why", "")),
                expected_signals=str(q.get("expected_signals", "")),
                source="validation",
                priority=_normalise_priority(q.get("priority"), "high"),
            ))
        result = ValidationResult(
            contradictions=[
                {  # pydantic will coerce
                    "finding_a": str(c.get("finding_a", "")),
                    "finding_b": str(c.get("finding_b", "")),
                    "explanation": str(c.get("explanation", "")),
                    "resolution": c.get("resolution"),
                }
                for c in (obj.get("contradictions") or [])
            ],
            hallucinations=[str(x) for x in (obj.get("hallucinations") or [])],
            gaps=[str(x) for x in (obj.get("gaps") or [])],
            recommend_more_investigation=new_questions,
        )
        self.mem.write_validation(result)
        self.mem.append_trace(TraceEntry(
            iteration=state.iteration_in_phase, kind="phase_transition",
            content=f"validation: {len(result.contradictions)} contradictions, "
                    f"{len(result.hallucinations)} hallucinations, "
                    f"{len(result.gaps)} gaps, "
                    f"{len(result.recommend_more_investigation)} new questions",
        ))
        return result

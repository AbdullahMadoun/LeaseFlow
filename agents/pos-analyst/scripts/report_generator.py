"""Phase 6 — synthesize the final markdown report.

A single LLM call. Reads everything on disk, returns markdown. The agent here
is constrained to the report-structure contract by the system prompt and the
phase instruction in prompts.py.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI

from analyst_agent import llm_call
from config import CONFIG
from memory import JobMemory
from prompts import REPORT_PHASE_INSTRUCTION, SYSTEM_PROMPT

log = logging.getLogger("pos.report")
_THINK_BLOCK_RE = re.compile(r"(?is)^<think>.*?</think>\s*")


def generate_report(client: OpenAI, mem: JobMemory) -> str:
    plan = mem.read_plan()
    findings = mem.read_findings()
    profile = mem.read_profile()
    ctx = mem.read_context_summary()
    validation = mem.read_validation()

    n_branches = 0
    if profile:
        for fp in profile.files:
            br = fp.detected_role.get("branch")
            if br:
                # Use the unique-count we already captured during profiling.
                col = next((c for c in fp.columns if c.name == br), None)
                if col and col.n_unique:
                    n_branches = max(n_branches, col.n_unique)

    payload = {
        "context_summary": ctx.model_dump() if ctx else {},
        "data_overview": {
            "files": [
                {
                    "name": fp.filename,
                    "rows": fp.n_rows,
                    "time_range": fp.time_range,
                    "detected_roles": fp.detected_role,
                    "quality_flags": fp.quality_flags,
                }
                for fp in (profile.files if profile else [])
            ],
            "n_branches_detected": n_branches,
        },
        "plan": plan.model_dump() if plan else {},
        "findings": [f.model_dump() for f in findings],
        "validation": validation.model_dump() if validation else {},
    }

    payload_json = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    if len(payload_json) > 120000:
        # Truncate the bodies of older findings rather than dropping any.
        for f in payload["findings"][:-30]:
            if isinstance(f, dict) and isinstance(f.get("body"), str) and len(f["body"]) > 400:
                f["body"] = f["body"][:400] + " …[truncated]"
        payload_json = json.dumps(payload, indent=2, ensure_ascii=False, default=str)

    user_msg = (
        f"{REPORT_PHASE_INSTRUCTION}\n\n"
        f"---- ANALYSIS PAYLOAD ----\n{payload_json}\n"
    )

    resp = llm_call(
        client,
        model=CONFIG.report_model_id,
        temperature=0.3,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    markdown = _strip_reasoning_preamble((resp.choices[0].message.content or "").strip())

    # Split off and persist the audit appendix; serve only the business-facing portion.
    main, audit = _split_audit_appendix(markdown)
    mem.write_evidence_map(audit or _build_fallback_audit(findings))
    mem.write_report(main)
    return main


def _split_audit_appendix(markdown: str) -> tuple[str, str]:
    marker = "## Evidence map (audit only)"
    idx = markdown.lower().find(marker.lower())
    if idx < 0:
        return markdown, ""
    return markdown[:idx].rstrip(), markdown[idx:].strip()


def _build_fallback_audit(findings: list[Any]) -> str:
    """If the model forgot the audit section, write a minimal one ourselves."""
    lines = ["## Evidence map (audit only)", ""]
    for f in findings:
        steps = ", ".join(str(s) for s in f.evidence_step_ids)
        lines.append(f"- {f.id}  q={f.question_id}  steps=[{steps}]  :: {f.title}")
    return "\n".join(lines)


def _strip_reasoning_preamble(markdown: str) -> str:
    return _THINK_BLOCK_RE.sub("", markdown).strip()

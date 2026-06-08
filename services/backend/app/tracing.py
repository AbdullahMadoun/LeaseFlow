"""Audit trail — every LLM call, rule fire, aggregation, and reconcile
writes a row to public.ai_traces.

Two entry points:
  - traced_llm_call(...): wraps a MiniMax call, captures prompt + raw
    response + parsed result + latency.
  - write_event(...): writes a non-LLM event (rule fire, aggregation,
    reconciliation result).

Failures in tracing never bubble up — the pipeline must not fail because
the audit log is down.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from .config import CONFIG
from .llm_client import _strip_fences, get_llm
from .supabase_client import get_client

log = logging.getLogger(__name__)


def _insert(row: dict) -> None:
    try:
        get_client().table("ai_traces").insert(row).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("ai_traces insert failed", extra={"err": str(e), "stage": row.get("stage")})


def write_event(
    *,
    loan_id: str,
    stage: str,
    kind: str,
    document_id: str | None = None,
    dimension: str | None = None,
    parsed: Any = None,
    error: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """Non-LLM event: rule fire, aggregation, reconciliation, extraction meta."""
    _insert({
        "loan_id": loan_id,
        "document_id": document_id,
        "stage": stage,
        "dimension": dimension,
        "kind": kind,
        "parsed": parsed if parsed is None or isinstance(parsed, (dict, list)) else {"value": parsed},
        "error": error,
        "duration_ms": duration_ms,
    })


async def traced_llm_call(
    *,
    loan_id: str,
    stage: str,
    system: str,
    user: str,
    dimension: str | None = None,
    document_id: str | None = None,
    json_mode: bool = True,
    temperature: float | None = None,
    model: str | None = None,
) -> tuple[Any, dict]:
    """Make a MiniMax call and persist the full trace. Returns (parsed, raw_message).

    `parsed` is the JSON-decoded object if json_mode=True, else the raw text.
    Raises if the call fails after one retry on JSON parse failure.
    """
    import json as _json

    client = get_llm()
    mdl = model or CONFIG.llm_model
    temp = temperature if temperature is not None else CONFIG.llm_temperature

    messages = [
        {"role": "system", "content": system + ("\n\nRespond with ONLY a valid JSON object. No prose, no markdown fences." if json_mode else "")},
        {"role": "user", "content": user},
    ]
    response_format = {"type": "json_object"} if json_mode else None

    started = time.time()
    last_err: Exception | None = None
    last_raw = ""
    parsed: Any = None
    raw_message: dict = {}

    for attempt in range(2):
        try:
            kwargs = {"model": mdl, "temperature": temp, "messages": messages}
            if response_format:
                kwargs["response_format"] = response_format
            resp = await client.chat.completions.create(**kwargs)
            raw_content = resp.choices[0].message.content or ""
            last_raw = raw_content
            raw_message = {
                "content": raw_content,
                "finish_reason": resp.choices[0].finish_reason,
                "usage": getattr(resp, "usage", None).model_dump() if getattr(resp, "usage", None) else None,
            }
            if json_mode:
                parsed = _json.loads(_strip_fences(raw_content))
            else:
                parsed = raw_content
            break
        except (_json.JSONDecodeError, Exception) as e:  # noqa: BLE001
            last_err = e
            log.warning("traced_llm_call attempt %d failed", attempt + 1, extra={
                "stage": stage, "err": str(e)[:300],
            })
            if attempt == 0 and json_mode and isinstance(e, _json.JSONDecodeError):
                messages.append({"role": "assistant", "content": last_raw})
                messages.append({"role": "user",
                                 "content": "Your previous response was not valid JSON. Respond with ONLY a valid JSON object."})
                continue
            break

    duration_ms = int((time.time() - started) * 1000)

    _insert({
        "loan_id": loan_id,
        "document_id": document_id,
        "stage": stage,
        "dimension": dimension,
        "kind": "llm_call",
        "prompt": {"system": system, "user": user, "response_format": response_format},
        "response_raw": raw_message or None,
        "parsed": parsed if isinstance(parsed, (dict, list)) else ({"value": parsed} if parsed is not None else None),
        "model": mdl,
        "duration_ms": duration_ms,
        "error": (f"{type(last_err).__name__}: {last_err}" if last_err and parsed is None else None),
    })

    if parsed is None and last_err is not None:
        raise last_err
    return parsed, raw_message

"""MiniMax LLM client via OpenAI-compatible SDK.

Same pattern as scripts/analyst_agent.py — OpenAI SDK pointed at api.minimax.io.
Exposes: complete() for free text, complete_json() for strict JSON with retry.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from openai import APIError, AsyncOpenAI

from .config import CONFIG

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=CONFIG.llm_api_key,
        base_url=CONFIG.llm_base_url,
        timeout=CONFIG.llm_timeout_s,
        max_retries=CONFIG.llm_max_retries,
    )


async def complete(system: str, user: str, *, temperature: float | None = None,
                   model: str | None = None) -> str:
    """Plain text completion."""
    client = get_llm()
    resp = await client.chat.completions.create(
        model=model or CONFIG.llm_model,
        temperature=temperature if temperature is not None else CONFIG.llm_temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


async def complete_json(system: str, user: str, *, temperature: float | None = None,
                        model: str | None = None, max_parse_retries: int = 1) -> dict[str, Any]:
    """JSON completion with strict parse + one retry on failure.

    MiniMax tool-use reliability varies; we enforce JSON via prompt and
    validate by parsing. On failure we retry once with an explicit
    "the previous response was not valid JSON" instruction.
    """
    client = get_llm()
    messages = [
        {"role": "system", "content": system + "\n\nRespond with ONLY a valid JSON object. No prose, no markdown fences."},
        {"role": "user", "content": user},
    ]
    last_err: Exception | None = None
    last_raw: str = ""
    for attempt in range(max_parse_retries + 1):
        try:
            resp = await client.chat.completions.create(
                model=model or CONFIG.llm_model,
                temperature=temperature if temperature is not None else CONFIG.llm_temperature,
                messages=messages,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or ""
            last_raw = raw
            return json.loads(_strip_fences(raw))
        except (json.JSONDecodeError, APIError) as e:
            last_err = e
            log.warning("complete_json attempt %d failed: %s", attempt + 1, e)
            if attempt < max_parse_retries:
                messages.append({"role": "assistant", "content": last_raw})
                messages.append({
                    "role": "user",
                    "content": "Your previous response was not valid JSON. Respond with ONLY a valid JSON object.",
                })
    raise RuntimeError(f"complete_json failed after {max_parse_retries + 1} attempts: {last_err}") from last_err


def _strip_fences(s: str) -> str:
    """Clean model output before JSON.loads:
      - Strip <think>...</think> blocks (MiniMax M2.7 and other thinking models).
      - Strip ```json ... ``` code fences.
      - Trim surrounding whitespace.
    """
    s = s.strip()

    # Strip thinking blocks. Keep everything AFTER the last </think>.
    if "</think>" in s:
        s = s.rsplit("</think>", 1)[1].strip()
    # Also handle orphaned opening tag (rare).
    if s.startswith("<think>"):
        s = s[len("<think>"):].strip()

    # Strip markdown fences.
    if s.startswith("```"):
        lines = s.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()

    return s

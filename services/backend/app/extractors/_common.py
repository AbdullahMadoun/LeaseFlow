"""Shared helpers for extractors: fast PDF→text via fitz, CSV preview,
and a generic `extract_with_schema` that makes the MiniMax call + validates.
"""
from __future__ import annotations

import io
import json
import logging
from typing import Any, TypeVar

import fitz  # PyMuPDF
import pandas as pd
from pydantic import BaseModel, ValidationError

from ..tracing import traced_llm_call

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Keep the prompt payload bounded. Financial docs rarely exceed a few KB;
# POS CSVs can be huge — we send only a preview.
PDF_CHARS_PER_PAGE_MAX = 8000
CSV_PREVIEW_ROWS = 40
CSV_PREVIEW_CHAR_MAX = 60_000


def pdf_to_text_by_page(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Return [(page_number, text), ...] using fitz. 1-indexed pages."""
    out: list[tuple[int, str]] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            text = page.get_text("text") or ""
            if len(text) > PDF_CHARS_PER_PAGE_MAX:
                text = text[:PDF_CHARS_PER_PAGE_MAX] + "\n…[truncated]"
            out.append((i + 1, text))
    return out


def pdf_text_block(pdf_bytes: bytes) -> str:
    """Format PDF as a single text block with page markers (what the LLM sees)."""
    pages = pdf_to_text_by_page(pdf_bytes)
    parts = []
    for n, text in pages:
        parts.append(f"<<PAGE {n}>>\n{text.strip()}")
    return "\n\n".join(parts)


def csv_preview_block(csv_bytes: bytes) -> tuple[str, dict[str, Any]]:
    """Return (preview_text, stats_dict) for a CSV. Preview is bounded."""
    df = pd.read_csv(io.BytesIO(csv_bytes))
    n_rows = len(df)
    # aggregate the numeric/time columns deterministically so the LLM sees
    # computed signals, not raw rows
    stats: dict[str, Any] = {"n_rows": n_rows, "columns": list(df.columns)}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            stats[f"{col}_sum"] = float(df[col].sum())
            stats[f"{col}_mean"] = float(df[col].mean())
    preview = df.head(CSV_PREVIEW_ROWS).to_csv(index=False)
    if len(preview) > CSV_PREVIEW_CHAR_MAX:
        preview = preview[:CSV_PREVIEW_CHAR_MAX] + "\n…[truncated]"
    return preview, stats


async def extract_with_schema(
    *,
    model_cls: type[T],
    loan_id: str,
    document_id: str | None,
    stage: str,
    system_prompt: str,
    user_payload: str,
    filename: str,
) -> T:
    """Call MiniMax with the user payload, validate against model_cls.

    On validation failure, re-ask once with the validation error as feedback.
    Final fallback: construct a minimal instance with confidence=0 and
    low_confidence_fields listing everything expected.
    """
    # Give MiniMax the target schema via its JSON-ish representation
    schema_hint = json.dumps(model_cls.model_json_schema(), ensure_ascii=False)

    user = (
        f"Extract from this document.\n\n"
        f"Filename: {filename}\n\n"
        f"Content:\n```\n{user_payload}\n```\n\n"
        f"Target JSON schema:\n```json\n{schema_hint}\n```\n\n"
        "Produce ONLY the JSON object. Include every numeric field with a source_pages "
        "array if the field has that attribute. If a field is genuinely missing or "
        "ambiguous in the document, leave it null and list it in meta.low_confidence_fields."
    )

    try:
        parsed, _ = await traced_llm_call(
            loan_id=loan_id,
            document_id=document_id,
            stage=stage,
            system=system_prompt,
            user=user,
            json_mode=True,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("extractor LLM failed", extra={"stage": stage, "err": str(e)[:300]})
        # Build a minimal "failed" instance — pipeline must continue
        return _failed_instance(model_cls, filename, error=str(e)[:200])

    validation_errors: list[dict] | None = None
    try:
        return model_cls.model_validate(parsed)
    except ValidationError as e:
        validation_errors = [
            {k: v for k, v in err.items() if k in ("loc", "msg", "type")}
            for err in e.errors()[:5]
        ]
        log.warning("extractor output failed validation; retrying once",
                    extra={"stage": stage, "errors": validation_errors[:3]})

    # One retry with error feedback
    retry_user = (
        user
        + "\n\nYour previous output FAILED schema validation. Fix these issues and "
        "return only the corrected JSON object:\n"
        + json.dumps(validation_errors)
    )
    try:
        parsed, _ = await traced_llm_call(
            loan_id=loan_id,
            document_id=document_id,
            stage=f"{stage}_retry",
            system=system_prompt,
            user=retry_user,
            json_mode=True,
        )
        return model_cls.model_validate(parsed)
    except Exception as e2:  # noqa: BLE001
        log.warning("extractor retry also failed", extra={"stage": stage, "err": str(e2)[:300]})
        return _failed_instance(model_cls, filename, error=str(e2)[:200])


def _failed_instance(model_cls: type[T], filename: str, *, error: str) -> T:
    """Construct a minimal instance signaling extraction failure.
    The pipeline continues and expert synthesis will see low confidence."""
    from ..schemas.documents import ExtractionMeta
    # All report types have a `meta` field; build with all fields at None/default
    try:
        return model_cls(
            meta=ExtractionMeta(
                confidence=0.0,
                low_confidence_fields=["all"],
                extraction_notes=[f"extractor_failed: {error}"],
                source_filename=filename,
            ),
        )  # type: ignore[call-arg]
    except Exception:
        # Shouldn't hit — all 4 report types have only meta as strictly required
        raise

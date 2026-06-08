"""/documents/* endpoints — classifier + utilities."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException

from .. import classifier
from ..supabase_client import signed_url

log = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/classify")
async def classify(body: dict) -> dict:
    """Given a storage_path to a just-uploaded doc, predict doc_type.

    Body:
      { "storage_path": "<merchant_id>/<loan_id>/<maybe-type>/<uuid>.<ext>" }

    Never raises 500. Downstream extractor or classifier errors degrade to
    `doc_type: "unknown"` with the error surfaced in `error`. Frontend can
    show the "pick manually" prompt in that case.
    """
    storage_path = body.get("storage_path")
    if not storage_path:
        raise HTTPException(status_code=400, detail="storage_path is required")
    fname = Path(storage_path).name

    # ----- Sign + download -----
    # Small retry loop on download: on immediate-after-upload, Storage can take
    # a beat to propagate through its CDN edge. ~3× with 0.5s backoff is fine.
    content: bytes | None = None
    download_err: str | None = None
    try:
        url = signed_url(storage_path)
    except Exception as e:  # noqa: BLE001
        return {
            "doc_type": "unknown", "confidence": 0.0, "file_name": fname,
            "signals": {}, "snippet": "",
            "error": f"signed_url_failed: {type(e).__name__}: {e}"[:300],
        }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(url)
                r.raise_for_status()
                content = r.content
                break
        except Exception as e:  # noqa: BLE001
            download_err = f"{type(e).__name__}: {e}"[:200]
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))

    if content is None:
        return {
            "doc_type": "unknown", "confidence": 0.0, "file_name": fname,
            "signals": {}, "snippet": "",
            "error": f"download_failed: {download_err}",
        }

    # ----- Classify (never allow this to 500) -----
    try:
        result = classifier.classify_bytes(content, fname)
    except Exception as e:  # noqa: BLE001
        log.warning("classifier crashed — returning unknown", extra={
            "classifier_err": f"{type(e).__name__}: {e}"[:300],
            "doc_file_name": fname, "content_size": len(content),
        })
        return {
            "doc_type": "unknown", "confidence": 0.0, "file_name": fname,
            "signals": {}, "snippet": "",
            "error": f"classifier_crashed: {type(e).__name__}: {e}"[:300],
        }

    result["file_name"] = fname
    # Keep "filename" key for backward compat with any frontend version
    # already using it.
    result["filename"] = fname

    # NOTE: Python's LogRecord has reserved names (filename, module, pathname,
    # lineno, ...). Passing them via `extra=` raises KeyError. Use prefixed
    # keys here.
    try:
        log.info("classified document", extra={
            "doc_file_name": fname,
            "classified_doc_type": result.get("doc_type"),
            "classifier_confidence": result.get("confidence"),
        })
    except Exception:
        pass  # never let logging crash the endpoint

    return result

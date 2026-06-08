"""Orchestrator — 3-phase pipeline.

PHASE A  extract_documents    one task per documents row
                              writes documents.analysis_report + ai_traces
PHASE B  dim fan-out           5 dims (pos, financial_docs, simah, sentiment, industry)
                              financial + pos aggregators read Phase A output
PHASE C  expert synthesis      deterministic scorer + LLM guardrail + hard floors

Race-free claims at each phase boundary ensure single-writer semantics.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from . import analyst_service
from . import expert
from .config import CONFIG
from .dims import REGISTRY as DIM_REGISTRY
from .extractors import REGISTRY as EXTRACTOR_REGISTRY
from .schemas import DimensionName, DimensionOutput
from .supabase_client import get_client, signed_url
from .tracing import write_event

log = logging.getLogger(__name__)

ALWAYS_RUN: tuple[DimensionName, ...] = ("simah", "sentiment", "industry")

DOC_DIM_MAP: dict[str, DimensionName] = {
    "pos_data": "pos",
    "bank_statement": "financial_docs",
    "financial_statement": "financial_docs",
}

# DEMO_MODE replay: merchant email → source loan_id to copy results from.
# Used only when CONFIG.demo_mode is True. Real upload, classification, and
# RLS all still run; only extraction + dims + synthesis are replaced by a
# paced replay of the source loan's cached data. See handoff/DEMO_MODE.md.
DEMO_TEMPLATES: dict[str, str] = {
    "ghazal.abdulrazzak@gmail.com": "13535ea2-47a2-46ba-90d7-b78377e73cf5",  # Qahwa → approved
    "gzrazak@gmail.com":            "db71e453-d67b-4baf-9544-1fc0f74d883b",  # Awful → denied
    "a-madoun@hotmail.com":         "490e4f40-5446-48c4-b8a5-f4c36d655c03",  # Iffy → manual_review
}


def decide_registered_dims(docs: list[dict]) -> list[DimensionName]:
    dims: set[DimensionName] = set(ALWAYS_RUN)
    for d in docs:
        if d["doc_type"] in DOC_DIM_MAP:
            dims.add(DOC_DIM_MAP[d["doc_type"]])
    return sorted(dims)


# ============================================================
# Entry point
# ============================================================

class RequiredDocumentsMissing(ValueError):
    """Raised when required documents aren't present. FastAPI maps to 422."""
    def __init__(self, missing: dict):
        self.missing = missing
        super().__init__(f"required documents missing: {missing}")


def _check_required_documents(docs: list[dict], policy: dict) -> dict:
    """Return {} if complete, else {missing_all_of: [...], missing_any_of: [[...], ...]}."""
    req = (policy or {}).get("required_documents") or {}
    uploaded_types = {d["doc_type"] for d in docs}
    missing_all: list[str] = [t for t in (req.get("all_of") or []) if t not in uploaded_types]
    missing_any: list[list[str]] = []
    for group in (req.get("any_of") or []):
        if not any(t in uploaded_types for t in group):
            missing_any.append(list(group))
    if not missing_all and not missing_any:
        return {}
    return {"missing_all_of": missing_all, "missing_any_of": missing_any,
            "uploaded_types": sorted(uploaded_types)}


def _load_active_policy(sb) -> dict:
    row = sb.table("risk_policies").select("rules").order("effective_from", desc=True).limit(1).execute().data
    return (row[0]["rules"] if row else {}) or {}


async def start_analysis(loan_id: str) -> dict:
    sb = get_client()
    loan = sb.table("loans").select("*").eq("id", loan_id).single().execute().data
    if not loan:
        raise ValueError(f"loan not found: {loan_id}")
    if loan["synthesis_status"] == "done":
        return {"status": "already_complete", "loan_id": loan_id,
                "registered_dimensions": loan.get("registered_dimensions") or []}

    merchant = sb.table("merchants").select("*").eq("id", loan["merchant_id"]).single().execute().data
    docs = sb.table("documents").select("*").eq("loan_id", loan_id).execute().data or []

    # Validate required documents against active risk_policy
    policy = _load_active_policy(sb)
    missing = _check_required_documents(docs, policy)
    if missing:
        write_event(loan_id=loan_id, stage="pipeline_blocked_missing_docs",
                    kind="rule", parsed=missing)
        raise RequiredDocumentsMissing(missing)

    registered = decide_registered_dims(docs)

    claim = sb.table("loans").update({
        "status": "analyzing",
        "registered_dimensions": registered,
        "analysis_started_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", loan_id).eq("status", "pending_analysis").execute()
    if not claim.data:
        if loan.get("status") in ("analyzing", "manual_review", "approved", "denied"):
            return {"status": "already_running", "loan_id": loan_id,
                    "registered_dimensions": loan.get("registered_dimensions") or registered}

    write_event(loan_id=loan_id, stage="pipeline_start", kind="rule",
                parsed={"registered_dimensions": registered, "doc_count": len(docs)})

    now = datetime.now(timezone.utc).isoformat()
    all_dims: list[DimensionName] = ["pos", "financial_docs", "simah", "sentiment", "industry"]
    sb.table("dimension_results").upsert(
        [{"loan_id": loan_id, "dimension": d,
          "status": "queued" if d in registered else "skipped",
          "updated_at": now} for d in all_dims],
        on_conflict="loan_id,dimension",
    ).execute()

    # DEMO replay: if this merchant's email is in DEMO_TEMPLATES and demo_mode
    # is on, spawn a paced replay from the source loan instead of the real
    # pipeline. Classification + upload + required-doc check already ran above.
    source_loan_id: str | None = None
    if CONFIG.demo_mode:
        merchant_email = await _lookup_merchant_email(sb, merchant.get("user_id"))
        source_loan_id = DEMO_TEMPLATES.get((merchant_email or "").lower())
        if source_loan_id:
            write_event(loan_id=loan_id, stage="demo_replay_dispatch", kind="rule",
                        parsed={"source_loan_id": source_loan_id,
                                "merchant_email": merchant_email})

    if source_loan_id:
        asyncio.create_task(_replay_from_source_loan(loan_id, loan, merchant, docs, source_loan_id))
        return {"status": "started", "loan_id": loan_id,
                "registered_dimensions": registered, "demo_replay": True}

    asyncio.create_task(_run_pipeline(loan_id, loan, merchant, docs, registered))
    return {"status": "started", "loan_id": loan_id, "registered_dimensions": registered}


async def _run_pipeline(loan_id: str, loan: dict, merchant: dict,
                        docs: list[dict], registered: list[DimensionName]) -> None:
    try:
        if docs:
            await _run_phase_a(loan_id, loan, docs)
        sb = get_client()
        docs = sb.table("documents").select("*").eq("loan_id", loan_id).execute().data or []
        ctx = {"loan": loan, "merchant": merchant, "documents": docs}
        asyncio.create_task(_start_supplemental_analyst(loan_id, loan, merchant, docs))
        sem = asyncio.Semaphore(CONFIG.pipeline_concurrency)

        async def _run_one(dim: DimensionName):
            async with sem:
                await _run_dim(loan_id, dim, ctx)

        await asyncio.gather(*[_run_one(d) for d in registered])
        await _maybe_synthesize(loan_id)
    except Exception as e:  # noqa: BLE001
        log.exception("pipeline crashed", extra={"loan_id": loan_id})
        sb = get_client()
        sb.table("loans").update({
            "synthesis_status": "error",
            "status": "manual_review",
        }).eq("id", loan_id).execute()
        write_event(loan_id=loan_id, stage="pipeline_crash", kind="rule",
                    error=f"{type(e).__name__}: {e}"[:500])


async def _start_supplemental_analyst(loan_id: str, loan: dict, merchant: dict, docs: list[dict]) -> None:
    try:
        await analyst_service.start_job_for_loan(loan_id, loan, merchant, docs)
    except Exception as e:  # noqa: BLE001
        log.warning("supplemental analyst start failed", extra={"loan_id": loan_id, "err": str(e)[:300]})
        write_event(
            loan_id=loan_id,
            stage="analyst_background_start_error",
            kind="aggregation",
            error=f"{type(e).__name__}: {e}"[:500],
        )


# ============================================================
# PHASE A — per-document extraction
# ============================================================

async def _run_phase_a(loan_id: str, loan: dict, docs: list[dict]) -> None:
    sem = asyncio.Semaphore(CONFIG.pipeline_concurrency)

    async def _extract_one(doc: dict):
        async with sem:
            await _extract_document(loan_id, loan, doc)

    await asyncio.gather(*[_extract_one(d) for d in docs])


async def _extract_document(loan_id: str, loan: dict, doc: dict) -> None:
    sb = get_client()
    doc_id = doc["id"]
    doc_type = doc["doc_type"]

    if doc.get("analysis_report") and doc.get("analysis_status") == "done":
        return

    sb.table("documents").update({"analysis_status": "processing"}).eq("id", doc_id).execute()

    extractor = EXTRACTOR_REGISTRY.get(doc_type)
    if extractor is None:
        log.warning("no extractor for doc_type", extra={"doc_type": doc_type, "doc_id": doc_id})
        sb.table("documents").update({
            "analysis_status": "error",
            "analysis_report": {"error": f"no extractor for doc_type={doc_type}"},
        }).eq("id", doc_id).execute()
        return

    try:
        content = await _download_doc(doc["storage_path"])
    except Exception as e:  # noqa: BLE001
        log.exception("doc download failed", extra={"doc_id": doc_id})
        sb.table("documents").update({
            "analysis_status": "error",
            "analysis_report": {"error": f"download_failed: {e}"[:300]},
        }).eq("id", doc_id).execute()
        return

    # ---- Tier 1 cache: per-doc extraction by content_hash ----
    import hashlib
    content_hash = hashlib.sha256(content).hexdigest()
    cached = (
        sb.table("documents")
        .select("analysis_report, extractor_schema_version")
        .eq("content_hash", content_hash)
        .eq("doc_type", doc_type)
        .eq("analysis_status", "done")
        .neq("id", doc_id)
        .limit(1)
        .execute()
        .data
    )
    if cached and cached[0].get("analysis_report") and not cached[0]["analysis_report"].get("error"):
        report = cached[0]["analysis_report"]
        sb.table("documents").update({
            "content_hash": content_hash,
            "analysis_status": "done",
            "analysis_report": report,
            "extractor_schema_version": cached[0].get("extractor_schema_version") or "v1",
        }).eq("id", doc_id).execute()
        write_event(
            loan_id=loan_id, document_id=doc_id,
            stage=f"extract_{doc_type}_cache_hit", kind="extraction",
            parsed={"content_hash": content_hash[:16],
                    "confidence": (report.get("meta") or {}).get("confidence")},
            duration_ms=0,
        )
        log.info("extraction cache hit", extra={
            "doc_id": doc_id, "doc_type": doc_type, "hash": content_hash[:16]})
        return

    # Miss — run the real extractor. Save hash so future uploads hit the cache.
    kwargs: dict[str, Any] = {
        "filename": doc["storage_path"].split("/")[-1],
        "loan_id": loan_id,
        "document_id": doc_id,
    }
    if doc_type == "pos_data":
        kwargs["csv_bytes"] = content
    else:
        kwargs["pdf_bytes"] = content
    if doc_type == "invoice":
        kwargs["requested_amount_sar"] = float(loan.get("amount_requested") or 0)

    started = datetime.now(timezone.utc)
    try:
        report = await extractor(**kwargs)
        report_dict = report.model_dump()
        sb.table("documents").update({
            "analysis_status": "done",
            "analysis_report": report_dict,
            "extractor_schema_version": (report_dict.get("meta") or {}).get("schema_version", "v1"),
        }).eq("id", doc_id).execute()
        write_event(
            loan_id=loan_id, document_id=doc_id,
            stage=f"extract_{doc_type}_done",
            kind="extraction",
            parsed={"confidence": (report_dict.get("meta") or {}).get("confidence"),
                    "low_confidence_fields": (report_dict.get("meta") or {}).get("low_confidence_fields", [])},
            duration_ms=int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        )
    except Exception as e:  # noqa: BLE001
        log.exception("extractor failed", extra={"doc_id": doc_id, "doc_type": doc_type})
        sb.table("documents").update({
            "analysis_status": "error",
            "analysis_report": {"error": f"{type(e).__name__}: {e}"[:500]},
        }).eq("id", doc_id).execute()


async def _download_doc(storage_path: str) -> bytes:
    url = signed_url(storage_path)
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content


# ============================================================
# PHASE B — dimension fan-out
# ============================================================

async def _run_dim(loan_id: str, dim: DimensionName, ctx: dict[str, Any]) -> None:
    sb = get_client()
    runner = DIM_REGISTRY[dim]
    started = datetime.now(timezone.utc)

    sb.table("dimension_results").update({"status": "processing"}).eq("loan_id", loan_id).eq("dimension", dim).execute()

    out: DimensionOutput | None = None
    err: str | None = None
    try:
        out = await asyncio.wait_for(runner(ctx), timeout=CONFIG.dim_task_timeout_s)
    except Exception as e:  # noqa: BLE001
        log.exception("dim failed", extra={"loan_id": loan_id, "dimension": dim})
        err = f"{type(e).__name__}: {e}"[:500]

    dur_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    if out is not None:
        sb.table("dimension_results").update({
            "status": "done",
            "score": out.score,
            "confidence": out.confidence,
            "dimension_version": out.dimension_version,
            "narrative": out.narrative,
            "result": out.model_dump(),
            "error_message": None,
        }).eq("loan_id", loan_id).eq("dimension", dim).execute()
        write_event(loan_id=loan_id, stage=f"dim_{dim}_done", dimension=dim,
                    kind="aggregation",
                    parsed={"score": out.score, "confidence": out.confidence,
                            "flags": out.flags},
                    duration_ms=dur_ms)
    else:
        sb.table("dimension_results").update({
            "status": "error",
            "error_message": err,
        }).eq("loan_id", loan_id).eq("dimension", dim).execute()
        write_event(loan_id=loan_id, stage=f"dim_{dim}_error", dimension=dim,
                    kind="aggregation", error=err, duration_ms=dur_ms)


# ============================================================
# PHASE C — synthesis claim
# ============================================================

async def _maybe_synthesize(loan_id: str) -> None:
    sb = get_client()
    loan = sb.table("loans").select("registered_dimensions, synthesis_status").eq("id", loan_id).single().execute().data
    if loan["synthesis_status"] in ("running", "done"):
        return

    registered = loan.get("registered_dimensions") or []
    rows = sb.table("dimension_results").select("dimension, status").eq("loan_id", loan_id).execute().data or []
    statuses = {r["dimension"]: r["status"] for r in rows}
    for d in registered:
        if statuses.get(d) not in ("done", "error", "skipped"):
            return

    claim = sb.table("loans").update({"synthesis_status": "running"}).eq("id", loan_id).eq("synthesis_status", "pending").execute()
    if not claim.data:
        return

    write_event(loan_id=loan_id, stage="synthesis_start", kind="rule")
    try:
        await expert.synthesize(loan_id)
    except Exception as e:  # noqa: BLE001
        log.exception("synthesis failed", extra={"loan_id": loan_id})
        sb.table("loans").update({
            "synthesis_status": "error",
            "status": "manual_review",
            "decision_payload": {
                "error": f"{type(e).__name__}: {e}"[:500],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }).eq("id", loan_id).execute()
        write_event(loan_id=loan_id, stage="synthesis_error", kind="rule",
                    error=f"{type(e).__name__}: {e}"[:500])


# ============================================================
# Status / trace reads
# ============================================================

async def get_status(loan_id: str) -> dict:
    sb = get_client()
    loan = sb.table("loans").select(
        "id, status, synthesis_status, created_at, "
        "analysis_started_at, analysis_completed_at, analyst_jobs"
    ).eq("id", loan_id).single().execute().data
    if not loan:
        raise ValueError(f"loan not found: {loan_id}")
    dims = sb.table("dimension_results").select(
        "dimension, status, score, confidence, narrative, error_message, updated_at"
    ).eq("loan_id", loan_id).execute().data or []
    docs = sb.table("documents").select(
        "id, doc_type, analysis_status, extractor_schema_version"
    ).eq("loan_id", loan_id).execute().data or []

    analyst_jobs = loan.get("analyst_jobs") or {}
    synced = await analyst_service.get_status_for_loan(loan_id)
    if synced:
        analyst_jobs = analyst_jobs.copy()
        analyst_jobs[synced.get("job_key", "analyst")] = synced

    # Compute durations in seconds
    submitted = _parse_ts(loan.get("created_at"))
    started = _parse_ts(loan.get("analysis_started_at"))
    completed = _parse_ts(loan.get("analysis_completed_at"))
    sub_to_dec = round((completed - submitted).total_seconds(), 2) if submitted and completed else None
    pipeline = round((completed - started).total_seconds(), 2) if started and completed else None

    return {
        "loan_id": loan_id,
        "loan_status": loan["status"],
        "synthesis_status": loan["synthesis_status"],
        "dimensions": dims,
        "documents": docs,
        "timing": {
            "submitted_at": loan.get("created_at"),
            "started_at": loan.get("analysis_started_at"),
            "completed_at": loan.get("analysis_completed_at"),
            "submission_to_decision_s": sub_to_dec,
            "pipeline_duration_s": pipeline,
        },
        "analyst_jobs": analyst_jobs,
    }


def _parse_ts(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


async def get_trace(loan_id: str) -> dict:
    sb = get_client()
    rows = sb.table("ai_traces").select("*").eq("loan_id", loan_id).order("created_at").execute().data or []
    docs = sb.table("documents").select(
        "id, doc_type, storage_path, analysis_status, analysis_report"
    ).eq("loan_id", loan_id).execute().data or []
    return {"loan_id": loan_id, "traces": rows, "documents": docs}


async def start_analyst(loan_id: str) -> dict:
    sb = get_client()
    loan = sb.table("loans").select("*").eq("id", loan_id).single().execute().data
    if not loan:
        raise ValueError(f"loan not found: {loan_id}")
    merchant = sb.table("merchants").select("*").eq("id", loan["merchant_id"]).single().execute().data
    docs = sb.table("documents").select("*").eq("loan_id", loan_id).execute().data or []
    return await analyst_service.start_job_for_loan(loan_id, loan, merchant, docs)


async def get_analyst_status(loan_id: str) -> dict:
    sb = get_client()
    loan = sb.table("loans").select("id").eq("id", loan_id).single().execute().data
    if not loan:
        raise ValueError(f"loan not found: {loan_id}")
    snapshot = await analyst_service.get_status_for_loan(loan_id)
    if not snapshot:
        raise ValueError(f"no analyst job registered for loan {loan_id}")
    return {"loan_id": loan_id, "analyst_job": snapshot}


async def get_analyst_report(loan_id: str) -> dict:
    sb = get_client()
    loan = sb.table("loans").select("id").eq("id", loan_id).single().execute().data
    if not loan:
        raise ValueError(f"loan not found: {loan_id}")
    return await analyst_service.get_report_for_loan(loan_id)


# ============================================================
# DEMO_MODE replay path — theatrical playback of a prior pipeline
# ============================================================

async def _lookup_merchant_email(sb, user_id: str | None) -> str | None:
    """Best-effort fetch of a merchant's auth email via Supabase admin API."""
    if not user_id:
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                f"{CONFIG.supabase_url}/auth/v1/admin/users/{user_id}",
                headers={"apikey": CONFIG.supabase_service_key,
                         "Authorization": f"Bearer {CONFIG.supabase_service_key}"},
            )
            if r.status_code >= 300:
                return None
            return r.json().get("email")
    except Exception:
        return None


def _substitute_demo_payload(payload: dict, source_loan: dict, new_loan: dict) -> dict:
    """Replace source item_description + amount in decision_payload text so the
    LLM reasoning doesn't leak the source merchant's specifics. Best-effort
    JSON-level string replace; falls back to original on failure."""
    import copy
    import json as _json
    try:
        src_item = (source_loan.get("item_description") or "").strip()
        new_item = (new_loan.get("item_description") or "").strip()
        src_amt = source_loan.get("amount_requested")
        new_amt = new_loan.get("amount_requested")
        raw = _json.dumps(copy.deepcopy(payload))
        if src_item and new_item and src_item != new_item:
            raw = raw.replace(src_item, new_item)
        if src_amt and new_amt:
            try:
                src_f, new_f = float(src_amt), float(new_amt)
                if abs(src_f - new_f) > 0.01:
                    raw = raw.replace(f"{src_f:,.0f}", f"{new_f:,.0f}")
                    raw = raw.replace(f"{int(src_f)}", f"{int(new_f)}")
            except (TypeError, ValueError):
                pass
        return _json.loads(raw)
    except Exception:  # noqa: BLE001
        return payload


async def _replay_from_source_loan(
    loan_id: str, loan: dict, merchant: dict,
    new_docs: list[dict], source_loan_id: str,
) -> None:
    """Paced theatrical replay of a prior successful pipeline run.

    Copies document analysis_reports, dim results, decision_payload, and
    ai_traces from source_loan_id onto the new loan. Fires Stream
    subscription + decision email on approval (background). Used by
    DEMO_MODE to keep the demo cadence consistent regardless of MiniMax
    latency.

    All code paths upstream of this — upload, classification, RLS, required-
    docs check — ran normally. Only extraction + dims + synthesis are
    substituted with cached data.
    """
    try:
        sb = get_client()
        src = sb.table("loans").select("*").eq("id", source_loan_id).single().execute().data
        if not src:
            log.warning("demo replay: source loan not found",
                        extra={"source_loan_id": source_loan_id, "loan_id": loan_id})
            return

        src_docs = sb.table("documents").select("*").eq("loan_id", source_loan_id).execute().data or []
        src_dims = sb.table("dimension_results").select("*").eq("loan_id", source_loan_id).execute().data or []
        src_traces = sb.table("ai_traces").select("*").eq("loan_id", source_loan_id).execute().data or []

        # Source reports keyed by doc_type (duplicates in new loan share the same source report)
        report_by_type: dict[str, dict] = {}
        for sd in src_docs:
            if sd.get("analysis_report") and sd.get("doc_type"):
                report_by_type.setdefault(sd["doc_type"], sd["analysis_report"])

        write_event(loan_id=loan_id, stage="demo_replay_begin", kind="rule",
                    parsed={"source_loan_id": source_loan_id,
                            "source_dims": len(src_dims),
                            "source_docs": len(src_docs)})

        # Pin registered_dimensions to the source set so the dim cards
        # displayed line up with the payload's per_dim scores.
        src_registered = src.get("registered_dimensions") or []
        if src_registered:
            sb.table("loans").update({"registered_dimensions": src_registered}) \
                .eq("id", loan_id).execute()
            # Mark dims NOT in source as skipped (so they don't hang at 'queued')
            all_dims = ("pos", "financial_docs", "simah", "sentiment", "industry")
            for dim in all_dims:
                if dim not in src_registered:
                    sb.table("dimension_results").update({"status": "skipped"}) \
                        .eq("loan_id", loan_id).eq("dimension", dim).execute()

        # Phase A-like: stamp new docs with source reports (match by doc_type)
        await asyncio.sleep(0.4)
        for doc in new_docs:
            patch: dict = {"analysis_status": "done"}
            report = report_by_type.get(doc.get("doc_type"))
            if report:
                patch["analysis_report"] = report
                patch["extractor_schema_version"] = "demo-replay-v1"
            sb.table("documents").update(patch).eq("id", doc["id"]).execute()
            await asyncio.sleep(0.35)

        # Phase B-like: walk dims queued → processing → done with source data
        src_dims_by_name = {d["dimension"]: d for d in src_dims}
        for dim in src_registered or []:
            sd = src_dims_by_name.get(dim)
            if not sd:
                continue
            final_status = sd.get("status") or "done"
            if final_status not in ("done", "error", "skipped"):
                final_status = "done"
            if final_status == "done":
                sb.table("dimension_results").update({"status": "processing"}) \
                    .eq("loan_id", loan_id).eq("dimension", dim).execute()
                await asyncio.sleep(0.35)
            sb.table("dimension_results").update({
                "status": final_status,
                "score": sd.get("score"),
                "confidence": sd.get("confidence"),
                "dimension_version": sd.get("dimension_version"),
                "narrative": sd.get("narrative"),
                "result": sd.get("result"),
                "analyst_job_id": None,
                "error_message": sd.get("error_message"),
            }).eq("loan_id", loan_id).eq("dimension", dim).execute()
            await asyncio.sleep(0.5)

        # Phase C: stamp decision, substituting item/amount refs so the
        # reasoning text fits the new loan.
        src_payload = src.get("decision_payload") or {}
        payload = _substitute_demo_payload(src_payload, src, loan)
        final = payload.get("final_decision") or {}
        final_status = (final.get("status") or src.get("status") or "manual_review")
        approved_amount = final.get("approved_amount") or src.get("approved_amount")
        monthly_payment = src.get("monthly_payment")
        # Rescale monthly payment roughly to the new amount if amounts differ
        try:
            if approved_amount and src.get("approved_amount") and monthly_payment:
                ratio = float(approved_amount) / float(src["approved_amount"])
                monthly_payment = round(float(monthly_payment) * ratio, 2)
        except (TypeError, ValueError):
            pass

        sb.table("loans").update({
            "synthesis_status": "done",
            "status": final_status,
            "approved_amount": approved_amount,
            "monthly_payment": monthly_payment,
            "decision_payload": payload,
            "analysis_completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", loan_id).execute()

        # Copy ai_traces for a populated admin timeline (drops IDs + timestamps)
        if src_traces:
            trace_rows = []
            for t in src_traces:
                row = {k: v for k, v in t.items()
                       if k not in ("id", "loan_id", "created_at", "updated_at")}
                row["loan_id"] = loan_id
                trace_rows.append(row)
            try:
                sb.table("ai_traces").insert(trace_rows).execute()
            except Exception as e:  # noqa: BLE001
                log.warning("demo replay: trace copy failed",
                            extra={"err": str(e)[:200]})

        write_event(loan_id=loan_id, stage="demo_replay_done", kind="rule",
                    parsed={"status": final_status, "approved_amount": approved_amount})

        # On approval, create real Stream subscription in background so the
        # decision card can render at ~5s; pay-now URL fills in a few seconds later.
        if final_status == "approved" and approved_amount:
            try:
                from .payments import install_schedule_for_loan
                loan_after = sb.table("loans").select("*").eq("id", loan_id).single().execute().data
                asyncio.create_task(install_schedule_for_loan(loan_id, loan_after))
            except Exception as e:  # noqa: BLE001
                log.warning("demo replay: stream schedule dispatch failed",
                            extra={"err": str(e)[:200]})

        # Decision email — approved only, background fire-and-forget.
        if final_status == "approved":
            try:
                from .notifications import send_decision_email
                email = await _lookup_merchant_email(sb, merchant.get("user_id"))
                if email:
                    asyncio.create_task(send_decision_email(
                        email, loan_id, payload, merchant.get("business_name")
                    ))
            except Exception as e:  # noqa: BLE001
                log.warning("demo replay: decision email dispatch failed",
                            extra={"err": str(e)[:200]})
        else:
            log.info("demo replay: decision email skipped — non-approval",
                     extra={"loan_id": loan_id, "status": final_status})

    except Exception as e:  # noqa: BLE001
        log.exception("demo replay crashed", extra={"loan_id": loan_id})
        try:
            sb = get_client()
            sb.table("loans").update({
                "synthesis_status": "error",
                "status": "manual_review",
            }).eq("id", loan_id).execute()
        except Exception:
            pass
        write_event(loan_id=loan_id, stage="demo_replay_crash", kind="rule",
                    error=f"{type(e).__name__}: {e}"[:500])

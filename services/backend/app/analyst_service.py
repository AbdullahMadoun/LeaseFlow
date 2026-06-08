"""Supplemental analyst service integration.

Submits a single-business restaurant/cafe underwriting bundle to the external
POS analyst, tracks the remote job, and proxies the final report when ready.
The underwriting pipeline does not block on this job.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import CONFIG
from .supabase_client import get_client
from .tracing import write_event

log = logging.getLogger(__name__)

ANALYST_JOB_KEY = "single_business_fnb_analyst"
ANALYST_TARGET_MINUTES = 5
ANALYST_HARD_CAP_MINUTES = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if CONFIG.analyst_api_key:
        headers["X-API-Key"] = CONFIG.analyst_api_key
    return headers


def _safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:400]


def _clean_report(doc: dict) -> dict[str, Any] | None:
    report = doc.get("analysis_report")
    if doc.get("analysis_status") != "done" or not report:
        return None
    if (report or {}).get("error"):
        return None
    return report


def _candidate_reports(docs: list[dict]) -> dict[str, list[dict]]:
    return {
        "bank_statement": [r for r in (_clean_report(d) for d in docs if d.get("doc_type") == "bank_statement") if r],
        "financial_statement": [r for r in (_clean_report(d) for d in docs if d.get("doc_type") == "financial_statement") if r],
        "pos_data": [r for r in (_clean_report(d) for d in docs if d.get("doc_type") == "pos_data") if r],
        "invoice": [r for r in (_clean_report(d) for d in docs if d.get("doc_type") == "invoice") if r],
    }


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes | None:
    if not rows:
        return None
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _merchant_profile_rows(loan: dict, merchant: dict, docs: list[dict]) -> list[dict[str, Any]]:
    return [{
        "loan_id": str(loan["id"]),
        "merchant_id": str(merchant["id"]),
        "business_name": merchant.get("business_name"),
        "cr_number": merchant.get("cr_number"),
        "phone": merchant.get("phone"),
        "google_maps_url": merchant.get("google_maps_url"),
        "amount_requested_sar": float(loan.get("amount_requested") or 0),
        "profit_rate": float(loan.get("profit_rate") or 0),
        "repayment_months": int(loan.get("repayment_months") or 0),
        "item_description": loan.get("item_description"),
        "uploaded_doc_types": ",".join(sorted({str(d.get("doc_type")) for d in docs if d.get("doc_type")})),
    }]


def _pos_daily_rows(reports: list[dict]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, report in enumerate(reports, start=1):
        for day in report.get("daily") or []:
            rows.append({
                "source_report": idx,
                "merchant_hint": report.get("merchant_hint"),
                "currency": report.get("currency", "SAR"),
                "date": day.get("date"),
                "revenue_sar": day.get("revenue_sar"),
                "txn_count": day.get("txn_count"),
                "avg_ticket_sar": day.get("avg_ticket_sar"),
            })
    return rows


def _pos_summary_rows(reports: list[dict]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, report in enumerate(reports, start=1):
        agg = report.get("aggregates") or {}
        rows.append({
            "source_report": idx,
            "merchant_hint": report.get("merchant_hint"),
            "period_start": report.get("period_start"),
            "period_end": report.get("period_end"),
            "currency": report.get("currency", "SAR"),
            "daily_revenue_avg_sar": agg.get("daily_revenue_avg_sar"),
            "monthly_revenue_est_sar": agg.get("monthly_revenue_est_sar"),
            "avg_ticket_sar": agg.get("avg_ticket_sar"),
            "peak_hours": "|".join(agg.get("peak_hours") or []),
            "seasonality": agg.get("seasonality"),
            "void_rate": agg.get("void_rate"),
            "refund_rate": agg.get("refund_rate"),
            "cash_mix_cash": (agg.get("cash_card_mix") or {}).get("cash"),
            "cash_mix_card": (agg.get("cash_card_mix") or {}).get("card"),
            "trend_90d": agg.get("trend_90d"),
            "confidence": (report.get("meta") or {}).get("confidence"),
        })
    return rows


def _bank_monthly_rows(reports: list[dict]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, report in enumerate(reports, start=1):
        for month in report.get("monthly") or []:
            rows.append({
                "source_report": idx,
                "bank_name": report.get("bank_name"),
                "account_holder": report.get("account_holder"),
                "period_start": report.get("period_start"),
                "period_end": report.get("period_end"),
                "currency": report.get("currency", "SAR"),
                "month": month.get("month"),
                "revenue_sar": month.get("revenue_sar"),
                "expenses_sar": month.get("expenses_sar"),
                "net_sar": month.get("net_sar"),
                "txn_count": month.get("txn_count"),
            })
    return rows


def _bank_summary_rows(reports: list[dict]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, report in enumerate(reports, start=1):
        agg = report.get("aggregates") or {}
        rows.append({
            "source_report": idx,
            "bank_name": report.get("bank_name"),
            "account_holder": report.get("account_holder"),
            "period_start": report.get("period_start"),
            "period_end": report.get("period_end"),
            "currency": report.get("currency", "SAR"),
            "monthly_revenue_avg_sar": agg.get("monthly_revenue_avg_sar"),
            "monthly_expenses_avg_sar": agg.get("monthly_expenses_avg_sar"),
            "monthly_net_avg_sar": agg.get("monthly_net_avg_sar"),
            "volatility": agg.get("volatility"),
            "trend": agg.get("trend"),
            "bounced_count": agg.get("bounced_count"),
            "overdraft_events": agg.get("overdraft_events"),
            "confidence": (report.get("meta") or {}).get("confidence"),
        })
    return rows


def _financial_rows(reports: list[dict]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, report in enumerate(reports, start=1):
        balance = report.get("balance_sheet") or {}
        income = report.get("income_statement") or {}
        ratios = report.get("ratios") or {}
        rows.append({
            "source_report": idx,
            "company_name": report.get("company_name"),
            "period_start": report.get("period_start"),
            "period_end": report.get("period_end"),
            "currency": report.get("currency", "SAR"),
            "total_assets_sar": balance.get("total_assets_sar"),
            "total_liabilities_sar": balance.get("total_liabilities_sar"),
            "equity_sar": balance.get("equity_sar"),
            "current_assets_sar": balance.get("current_assets_sar"),
            "current_liabilities_sar": balance.get("current_liabilities_sar"),
            "revenue_sar": income.get("revenue_sar"),
            "cogs_sar": income.get("cogs_sar"),
            "opex_sar": income.get("opex_sar"),
            "net_profit_sar": income.get("net_profit_sar"),
            "current_ratio": ratios.get("current_ratio"),
            "debt_to_equity": ratios.get("debt_to_equity"),
            "gross_margin": ratios.get("gross_margin"),
            "net_margin": ratios.get("net_margin"),
            "confidence": (report.get("meta") or {}).get("confidence"),
        })
    return rows


def _invoice_rows(reports: list[dict]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, report in enumerate(reports, start=1):
        lines = report.get("line_items") or [{}]
        for line in lines:
            rows.append({
                "source_report": idx,
                "vendor_name": report.get("vendor_name"),
                "vendor_vat": report.get("vendor_vat"),
                "invoice_number": report.get("invoice_number"),
                "issue_date": report.get("issue_date"),
                "currency": report.get("currency", "SAR"),
                "item_category": report.get("item_category"),
                "matches_requested_amount": report.get("matches_requested_amount"),
                "subtotal_sar": report.get("subtotal_sar"),
                "vat_sar": report.get("vat_sar"),
                "total_sar": report.get("total_sar"),
                "description": line.get("description"),
                "quantity": line.get("quantity"),
                "unit_price_sar": line.get("unit_price_sar"),
                "line_total_sar": line.get("total_sar"),
                "confidence": (report.get("meta") or {}).get("confidence"),
            })
    return rows


def _build_context(loan: dict, merchant: dict, reports: dict[str, list[dict]]) -> str:
    available = [key for key, items in reports.items() if items]
    return "\n".join([
        "# LeaseFlow Analyst Brief",
        "",
        "This upload represents a single restaurant or cafe business over time.",
        "Analyze it as one operator, not as a multi-merchant portfolio, unless a file explicitly proves otherwise.",
        "",
        f"- Merchant: {merchant.get('business_name') or 'Unknown merchant'}",
        f"- Commercial registration: {merchant.get('cr_number') or 'unknown'}",
        f"- Google Maps URL: {merchant.get('google_maps_url') or 'not provided'}",
        f"- Requested financing amount: SAR {float(loan.get('amount_requested') or 0):,.2f}",
        f"- Repayment months: {int(loan.get('repayment_months') or 0)}",
        f"- Profit rate: {float(loan.get('profit_rate') or 0):.4f}",
        f"- Financed item: {loan.get('item_description') or 'not provided'}",
        f"- Structured sources included: {', '.join(available) if available else 'none'}",
        "",
        "Primary questions:",
        "- Is this business operationally stable enough to support the requested financing?",
        "- What liquidity, cash conversion, refund, or volatility risks stand out?",
        "- What signals most strongly support or weaken underwriting confidence?",
        "- Keep the analysis concise and decision-useful for an admin reviewer.",
    ])


def _prepare_submission(loan: dict, merchant: dict, docs: list[dict]) -> dict[str, Any] | None:
    reports = _candidate_reports(docs)
    has_extracted_signal = any(reports[key] for key in ("pos_data", "bank_statement", "financial_statement", "invoice"))
    if not has_extracted_signal:
        return None
    files: list[tuple[str, tuple[str, bytes, str]]] = []

    file_rows = [
        ("merchant_profile.csv", _merchant_profile_rows(loan, merchant, docs)),
        ("pos_daily.csv", _pos_daily_rows(reports["pos_data"])),
        ("pos_summary.csv", _pos_summary_rows(reports["pos_data"])),
        ("bank_monthly.csv", _bank_monthly_rows(reports["bank_statement"])),
        ("bank_summary.csv", _bank_summary_rows(reports["bank_statement"])),
        ("financial_statement.csv", _financial_rows(reports["financial_statement"])),
        ("invoice_lines.csv", _invoice_rows(reports["invoice"])),
    ]

    for filename, rows in file_rows:
        payload = _csv_bytes(rows)
        if payload is not None:
            files.append(("files", (filename, payload, "text/csv")))

    if not files:
        return None

    meta = {
        "dataset_kind": "leaseflow_single_business_underwriting",
        "currency": "SAR",
        "synthetic": False,
        "analysis_time_target_minutes": ANALYST_TARGET_MINUTES,
        "analysis_time_hard_cap_minutes": ANALYST_HARD_CAP_MINUTES,
        "analysis_time_notes": "Prefer completion within 5 minutes. Hard stop at 30 minutes.",
    }

    return {
        "context": _build_context(loan, merchant, reports),
        "meta": meta,
        "files": files,
        "file_names": [item[1][0] for item in files],
    }


def _persist_snapshot(loan_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    sb = get_client()
    loan = sb.table("loans").select("analyst_jobs").eq("id", loan_id).single().execute().data or {}
    analyst_jobs = (loan.get("analyst_jobs") or {}).copy()
    analyst_jobs[ANALYST_JOB_KEY] = snapshot
    sb.table("loans").update({"analyst_jobs": analyst_jobs}).eq("id", loan_id).execute()
    return analyst_jobs


def _current_snapshot(loan_id: str) -> dict[str, Any] | None:
    loan = get_client().table("loans").select("analyst_jobs").eq("id", loan_id).single().execute().data
    jobs = (loan or {}).get("analyst_jobs") or {}
    return jobs.get(ANALYST_JOB_KEY)


async def start_job_for_loan(loan_id: str, loan: dict, merchant: dict, docs: list[dict]) -> dict[str, Any]:
    existing = (_current_snapshot(loan_id) or ((loan.get("analyst_jobs") or {}).get(ANALYST_JOB_KEY)) or {}).copy()
    if existing.get("job_id") and existing.get("status") in {"queued", "running", "done"}:
        return existing

    prepared = _prepare_submission(loan, merchant, docs)
    if prepared is None:
        snapshot = {
            "job_key": ANALYST_JOB_KEY,
            "eligible": False,
            "status": "skipped",
            "phase": None,
            "job_id": None,
            "submitted_at": None,
            "updated_at": _now_iso(),
            "report_ready": False,
            "file_names": [],
            "error": "No structured analyst bundle could be prepared from extracted documents.",
        }
        _persist_snapshot(loan_id, snapshot)
        write_event(
            loan_id=loan_id,
            stage="analyst_submission_skipped",
            kind="rule",
            parsed={"job_key": ANALYST_JOB_KEY, "reason": "no_structured_bundle"},
        )
        return snapshot

    snapshot = {
        "job_key": ANALYST_JOB_KEY,
        "eligible": True,
        "status": "submitting",
        "phase": "submit",
        "job_id": None,
        "submitted_at": None,
        "updated_at": _now_iso(),
        "report_ready": False,
        "file_names": prepared["file_names"],
        "error": None,
    }
    _persist_snapshot(loan_id, snapshot)

    try:
        data = {
            "context": prepared["context"],
            "meta": json.dumps(prepared["meta"]),
        }
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{CONFIG.analyst_api_url.rstrip('/')}/jobs",
                headers=_headers(),
                data=data,
                files=prepared["files"],
            )
            resp.raise_for_status()
            created = resp.json()

        snapshot.update({
            "status": created.get("status", "queued"),
            "phase": "created",
            "job_id": created.get("job_id"),
            "submitted_at": created.get("created_at") or _now_iso(),
            "updated_at": _now_iso(),
        })
        _persist_snapshot(loan_id, snapshot)
        write_event(
            loan_id=loan_id,
            stage="analyst_submission_started",
            kind="aggregation",
            parsed={
                "job_key": ANALYST_JOB_KEY,
                "job_id": snapshot.get("job_id"),
                "file_names": prepared["file_names"],
            },
        )
        return snapshot
    except Exception as exc:  # noqa: BLE001
        snapshot.update({
            "status": "error",
            "phase": "submit",
            "updated_at": _now_iso(),
            "error": _safe_error(exc),
        })
        _persist_snapshot(loan_id, snapshot)
        write_event(
            loan_id=loan_id,
            stage="analyst_submission_error",
            kind="aggregation",
            error=snapshot["error"],
            parsed={"job_key": ANALYST_JOB_KEY},
        )
        return snapshot


async def sync_job_for_loan(loan_id: str) -> dict[str, Any] | None:
    snapshot = _current_snapshot(loan_id)
    if not snapshot or not snapshot.get("job_id"):
        return snapshot
    if snapshot.get("status") in {"done", "failed", "skipped"}:
        return snapshot

    job_id = str(snapshot["job_id"])
    try:
        timeout = httpx.Timeout(5.0, connect=2.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{CONFIG.analyst_api_url.rstrip('/')}/jobs/{job_id}",
                headers=_headers(),
            )
            resp.raise_for_status()
            remote = resp.json()

        snapshot.update({
            "status": remote.get("status", snapshot.get("status")),
            "phase": remote.get("phase", snapshot.get("phase")),
            "updated_at": remote.get("updated_at") or _now_iso(),
            "error": remote.get("error"),
            "step_counter": remote.get("step_counter"),
            "iteration_in_phase": remote.get("iteration_in_phase"),
            "report_ready": remote.get("status") == "done",
        })
        _persist_snapshot(loan_id, snapshot)
        return snapshot
    except Exception as exc:  # noqa: BLE001
        err = _safe_error(exc)
        log.warning("analyst sync failed", extra={"loan_id": loan_id, "err": err})
        write_event(
            loan_id=loan_id,
            stage="analyst_status_sync_error",
            kind="aggregation",
            error=err,
            parsed={"job_key": ANALYST_JOB_KEY, "job_id": job_id},
        )
        return snapshot


async def get_status_for_loan(loan_id: str) -> dict[str, Any] | None:
    return await sync_job_for_loan(loan_id)


async def get_report_for_loan(loan_id: str) -> dict[str, Any]:
    snapshot = _current_snapshot(loan_id)
    if not snapshot or not snapshot.get("job_id"):
        raise ValueError(f"no analyst job registered for loan {loan_id}")

    snapshot = await sync_job_for_loan(loan_id) or snapshot
    if snapshot.get("status") != "done":
        raise RuntimeError(
            f"analyst job not done (status={snapshot.get('status')}, phase={snapshot.get('phase')})"
        )

    job_id = str(snapshot["job_id"])
    timeout = httpx.Timeout(30.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            f"{CONFIG.analyst_api_url.rstrip('/')}/jobs/{job_id}/report",
            headers=_headers(),
        )
        resp.raise_for_status()
        report_md = resp.text

    snapshot["report_ready"] = True
    snapshot["updated_at"] = _now_iso()
    _persist_snapshot(loan_id, snapshot)

    return {
        "loan_id": loan_id,
        "job_key": ANALYST_JOB_KEY,
        "job_id": job_id,
        "status": snapshot.get("status"),
        "phase": snapshot.get("phase"),
        "report_markdown": report_md,
    }


async def healthcheck() -> dict[str, Any]:
    if not CONFIG.analyst_api_url:
        return {"configured": False, "reachable": False, "error": "ANALYST_API_URL is empty"}
    try:
        timeout = httpx.Timeout(5.0, connect=2.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{CONFIG.analyst_api_url.rstrip('/')}/health", headers=_headers())
            resp.raise_for_status()
            payload = resp.json()
        return {
            "configured": True,
            "reachable": True,
            "model": payload.get("model"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "configured": True,
            "reachable": False,
            "error": _safe_error(exc),
        }

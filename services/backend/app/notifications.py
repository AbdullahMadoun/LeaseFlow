"""Email notifications via Resend. Fire-and-forget from the pipeline."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import CONFIG

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


async def _send(to_email: str, subject: str, html: str) -> None:
    if not CONFIG.notifications_enabled:
        log.info("notifications disabled — skipping", extra={"to": to_email, "subject": subject})
        return
    if not CONFIG.resend_api_key:
        log.warning("RESEND_API_KEY unset — skipping email", extra={"to": to_email})
        return
    payload = {
        "from": CONFIG.notifications_from,
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                RESEND_URL,
                json=payload,
                headers={"Authorization": f"Bearer {CONFIG.resend_api_key}"},
            )
            if r.status_code >= 300:
                log.warning("resend non-2xx", extra={"status": r.status_code, "body": r.text[:300]})
            else:
                log.info("email sent", extra={"to": to_email, "subject": subject})
    except Exception as e:  # noqa: BLE001 — never let email fail the pipeline
        log.exception("email send failed", extra={"err": str(e), "to": to_email})


def _fmt_amount(n: Any) -> str:
    try:
        return f"{float(n):,.0f}"
    except Exception:
        return str(n)


async def send_decision_email(to_email: str, loan_id: str, decision: dict,
                              merchant_name: str | None = None) -> None:
    final = decision.get("final_decision") or {}
    status = final.get("status", "pending")
    amt = final.get("approved_amount")
    reasoning = (decision.get("llm_response") or {}).get("reasoning") or ""

    greeting = f"Hi {merchant_name}," if merchant_name else "Hi,"
    subject_map = {
        "approved":      "Your LeaseFlow application was approved",
        "denied":        "Update on your LeaseFlow application",
        "manual_review": "Your LeaseFlow application is under review",
    }
    subject = subject_map.get(status, "Update on your LeaseFlow application")

    if status == "approved":
        body = f"""<p>{greeting}</p>
<p>Good news — your lease-to-own application (#{loan_id[:8]}) has been <strong>approved</strong>
for <strong>SAR {_fmt_amount(amt)}</strong>.</p>
<p>{reasoning}</p>
<p>You can log in to review the terms and next steps.</p>
<p>— LeaseFlow</p>"""
    elif status == "denied":
        body = f"""<p>{greeting}</p>
<p>Thank you for applying. After reviewing your application (#{loan_id[:8]}),
we are not able to extend financing at this time.</p>
<p>{reasoning}</p>
<p>— LeaseFlow</p>"""
    else:
        body = f"""<p>{greeting}</p>
<p>Your application (#{loan_id[:8]}) needs a quick manual review from our team.
We'll be in touch shortly.</p>
<p>— LeaseFlow</p>"""

    await _send(to_email, subject, body)


async def send_payment_receipt_email(to_email: str, loan_id: str,
                                     installment_number: int, amount_sar: float,
                                     merchant_name: str | None = None) -> None:
    greeting = f"Hi {merchant_name}," if merchant_name else "Hi,"
    subject = f"Payment received · installment #{installment_number}"
    body = f"""<p>{greeting}</p>
<p>We received your payment of <strong>SAR {_fmt_amount(amount_sar)}</strong> for
installment #{installment_number} on loan #{loan_id[:8]}.</p>
<p>Thank you — you can view your full repayment schedule in the app.</p>
<p>— LeaseFlow</p>"""
    await _send(to_email, subject, body)


async def send_manual_override_email(to_email: str, loan_id: str, status: str,
                                     approved_amount: float | None,
                                     merchant_name: str | None = None) -> None:
    greeting = f"Hi {merchant_name}," if merchant_name else "Hi,"
    if status == "approved":
        subject = "Your LeaseFlow application was approved"
        body = f"""<p>{greeting}</p>
<p>Our team has approved your application (#{loan_id[:8]}) for
<strong>SAR {_fmt_amount(approved_amount)}</strong>.</p>
<p>— LeaseFlow</p>"""
    elif status == "denied":
        subject = "Update on your LeaseFlow application"
        body = f"""<p>{greeting}</p>
<p>After review, we are not able to approve your application (#{loan_id[:8]}) at this time.</p>
<p>— LeaseFlow</p>"""
    else:
        return  # no email for other transitions
    await _send(to_email, subject, body)

"""/webhooks/stream and /installments/* endpoints.

Stream event shape (https://docs.streampay.sa/webhooks):

  {
    "event_type":  "PAYMENT_SUCCEEDED" | "PAYMENT_FAILED" | "INVOICE_COMPLETED" | ...,
    "entity_type": "PAYMENT" | "INVOICE" | "SUBSCRIPTION",
    "entity_id":   "uuid",
    "entity_url":  "https://.../api/v2/{type}/{id}",
    "status":      "SUCCEEDED" | "FAILED" | ...,
    "data":        { "invoice": {id,url}, "payment": {id,url}, "payment_link": {...}, "metadata": {...} },
    "timestamp":   "2026-..."
  }

Signature header: `Stream-Signature: t=<unix>,v1=<hex_hmac_sha256>`
We accept any of {`stream-signature`, `x-stream-signature`, `signature`} to be
robust to header-name drift.
"""
from __future__ import annotations

import json as _json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from ..notifications import send_payment_receipt_email
from ..payments import StreamAPIError, get_stream_client
from ..supabase_client import get_client
from ..tracing import write_event

log = logging.getLogger(__name__)

router = APIRouter(tags=["payments"])


PAYMENT_SUCCESS_EVENTS = {"PAYMENT_SUCCEEDED", "PAYMENT_MARKED_AS_PAID", "INVOICE_COMPLETED"}
PAYMENT_FAIL_EVENTS = {"PAYMENT_FAILED", "SUBSCRIPTION_CYCLE_RENEWAL_FAILED"}
PAYMENT_CANCEL_EVENTS = {"PAYMENT_CANCELED", "INVOICE_CANCELED"}
# INVOICE_CREATED (and _UPDATED / _SENT) feed `installments.stream_payment_url`
# so the merchant-side Payments page can render a "Pay now" link per cycle.
INVOICE_LINK_EVENTS = {"INVOICE_CREATED", "INVOICE_UPDATED", "INVOICE_SENT"}
SUBSCRIPTION_STATUS_EVENTS = {
    "SUBSCRIPTION_ACTIVATED": "ACTIVE",
    "SUBSCRIPTION_INACTIVATED": "INACTIVE",
    "SUBSCRIPTION_CANCELED": "CANCELED",
    "SUBSCRIPTION_FROZEN": "FROZEN",
}


@router.post("/webhooks/stream")
async def stream_webhook(
    request: Request,
    stream_signature: str | None = Header(default=None, alias="Stream-Signature"),
    x_stream_signature: str | None = Header(default=None, alias="X-Stream-Signature"),
    signature: str | None = Header(default=None, alias="Signature"),
):
    payload = await request.body()
    stream = get_stream_client()
    sig = stream_signature or x_stream_signature or signature
    if not stream.verify_webhook(payload, sig):
        log.warning("stream webhook signature verification FAILED")
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        body = _json.loads(payload.decode() or "{}")
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON")

    event_type = str(body.get("event_type") or "").upper()
    entity_type = str(body.get("entity_type") or "").upper()
    entity_id = body.get("entity_id")
    data = body.get("data") or {}

    log.info("stream webhook received", extra={
        "event_type": event_type, "entity_type": entity_type, "entity_id": entity_id,
    })

    sb = get_client()

    # Subscription status events — update loan row, no installment impact.
    if event_type in SUBSCRIPTION_STATUS_EVENTS and entity_type == "SUBSCRIPTION":
        return _handle_subscription_status(sb, entity_id, SUBSCRIPTION_STATUS_EVENTS[event_type])

    # Payment-success events — mark next pending installment paid.
    if event_type in PAYMENT_SUCCESS_EVENTS:
        return await _handle_payment_success(sb, stream, event_type, body, data)

    if event_type in PAYMENT_FAIL_EVENTS:
        return await _handle_payment_failure(sb, stream, event_type, body, data)

    if event_type in PAYMENT_CANCEL_EVENTS:
        log.info("stream cancel event ignored (no-op)", extra={"event_type": event_type})
        return {"ok": True, "event_type": event_type, "status": "ignored"}

    # Invoice lifecycle events with a URL — populate stream_payment_url on the
    # next pending installment so merchants can click "Pay now" in the UI.
    if event_type in INVOICE_LINK_EVENTS:
        return await _handle_invoice_link(sb, stream, event_type, body, data)

    log.info("stream webhook unknown event", extra={"event_type": event_type})
    return {"ok": False, "reason": "unknown_event", "event_type": event_type}


async def _handle_invoice_link(sb, stream, event_type: str, body: dict, data: dict) -> dict:
    """Map an invoice event onto an installment and stash the pay-now URL.

    For subscription renewals Stream fires INVOICE_CREATED per cycle. We look
    up the subscription, find the first still-unlinked (or still-pending)
    installment for that loan, and patch it with invoice_id + checkout URL.
    """
    subscription_id, invoice_id, _ = await _resolve_subscription_context(
        stream, event_type, body, data,
    )
    if not subscription_id or not invoice_id:
        return {"ok": False, "reason": "missing_ids", "event_type": event_type}

    loan = sb.table("loans").select("id") \
        .eq("stream_subscription_id", subscription_id).limit(1).execute().data
    if not loan:
        return {"ok": False, "reason": "loan_not_found", "subscription_id": subscription_id}
    loan_id = loan[0]["id"]

    # Fetch the invoice to get the hosted checkout URL (`url` field).
    invoice_url: str | None = (data.get("invoice") or {}).get("url")
    if not invoice_url and stream.is_live:
        try:
            inv = await stream.get_invoice(invoice_id)
            invoice_url = inv.get("url")
        except StreamAPIError as e:
            log.warning("invoice lookup failed",
                        extra={"invoice_id": invoice_id, "err": str(e)[:200]})

    # Prefer the installment already bound to this invoice (retry/update path),
    # otherwise pick the lowest-numbered pending installment that doesn't yet
    # have any stream URL recorded.
    bound = sb.table("installments").select("id, installment_number") \
        .eq("stream_invoice_id", invoice_id).limit(1).execute().data
    if bound:
        target_id = bound[0]["id"]
    else:
        pending = sb.table("installments").select("id, installment_number") \
            .eq("loan_id", loan_id).eq("status", "pending") \
            .is_("stream_invoice_id", "null") \
            .order("installment_number").limit(1).execute().data
        if not pending:
            return {"ok": True, "event_type": event_type, "status": "no_target"}
        target_id = pending[0]["id"]

    patch: dict = {"stream_invoice_id": invoice_id}
    if invoice_url:
        patch["stream_payment_url"] = invoice_url
        patch["stream_payment_link_id"] = invoice_id  # reuse legacy col as id reference
    sb.table("installments").update(patch).eq("id", target_id).execute()

    return {"ok": True, "event_type": event_type,
            "loan_id": loan_id, "installment_id": target_id,
            "url_set": bool(invoice_url)}


# ---------- handlers --------------------------------------------------------

async def _handle_payment_success(sb, stream, event_type: str, body: dict, data: dict) -> dict:
    """Advance the next pending installment for the subscription this event
    came from. Duplicate deliveries are safe — we conditionally UPDATE only
    pending rows, and a re-delivery of the same payment_id is detected."""
    subscription_id, invoice_id, payment_id = await _resolve_subscription_context(
        stream, event_type, body, data,
    )

    if not subscription_id:
        log.warning("stream webhook without resolvable subscription", extra={
            "event_type": event_type, "entity_id": body.get("entity_id"),
        })
        return {"ok": False, "reason": "no_subscription_id"}

    loan = sb.table("loans").select("id, merchant_id, amount_paid") \
        .eq("stream_subscription_id", subscription_id).limit(1).execute().data
    if not loan:
        log.warning("stream webhook: no loan matches subscription", extra={
            "subscription_id": subscription_id,
        })
        return {"ok": False, "reason": "loan_not_found"}
    loan = loan[0]
    loan_id = loan["id"]

    # Dedupe by payment_id first (strongest signal), then invoice_id.
    if payment_id:
        hit = sb.table("installments").select("id") \
            .eq("stream_payment_id", payment_id).limit(1).execute().data
        if hit:
            log.info("stream webhook re-delivery by payment_id, ignored", extra={
                "payment_id": payment_id, "installment_id": hit[0]["id"],
            })
            return {"ok": True, "idempotent": True, "installment_id": hit[0]["id"]}

    if invoice_id:
        hit = sb.table("installments").select("id") \
            .eq("stream_invoice_id", invoice_id).limit(1).execute().data
        if hit:
            log.info("stream webhook re-delivery by invoice_id, ignored", extra={
                "invoice_id": invoice_id, "installment_id": hit[0]["id"],
            })
            return {"ok": True, "idempotent": True, "installment_id": hit[0]["id"]}

    # Next pending installment (lowest installment_number still 'pending').
    pending = sb.table("installments").select("*") \
        .eq("loan_id", loan_id).eq("status", "pending") \
        .order("installment_number").limit(1).execute().data
    if not pending:
        log.info("stream payment success but no pending installments", extra={"loan_id": loan_id})
        return {"ok": True, "status": "no_pending", "loan_id": loan_id}

    inst = pending[0]
    amount = _safe_amount(data, default=float(inst["amount_sar"]))
    paid_at = body.get("timestamp") or datetime.now(timezone.utc).isoformat()

    patch = {
        "status": "paid",
        "paid_at": paid_at,
        "paid_amount_sar": amount,
        "payment_method": _extract_payment_method(data),
        "transaction_ref": payment_id,
        "stream_invoice_id": invoice_id,
        "stream_payment_id": payment_id,
    }
    upd = (
        sb.table("installments").update(patch)
        .eq("id", inst["id"]).eq("status", "pending").execute()
    )
    if not upd.data:
        log.info("stream webhook lost race to mark paid", extra={"installment_id": inst["id"]})
        return {"ok": True, "idempotent": True, "installment_id": inst["id"]}

    write_event(
        loan_id=loan_id, stage="installment_paid", kind="rule",
        parsed={
            "installment_id": inst["id"],
            "installment_number": inst["installment_number"],
            "amount_sar": amount,
            "stream_event_type": event_type,
            "stream_payment_id": payment_id,
            "stream_invoice_id": invoice_id,
        },
    )
    _bump_amount_paid(sb, loan_id, amount)

    try:
        await _send_receipt(sb, inst, amount)
    except Exception as e:  # noqa: BLE001
        log.warning("receipt email skipped", extra={"err": str(e)})

    return {
        "ok": True, "event_type": event_type,
        "loan_id": loan_id, "installment_id": inst["id"],
        "installment_number": inst["installment_number"],
    }


async def _handle_payment_failure(sb, stream, event_type: str, body: dict, data: dict) -> dict:
    """Record a failure against the subscription. Installment stays pending
    (Stream will retry per its own schedule)."""
    subscription_id, _invoice_id, payment_id = await _resolve_subscription_context(
        stream, event_type, body, data,
    )
    if not subscription_id:
        return {"ok": False, "reason": "no_subscription_id"}

    loan = sb.table("loans").select("id") \
        .eq("stream_subscription_id", subscription_id).limit(1).execute().data
    if not loan:
        return {"ok": False, "reason": "loan_not_found"}

    write_event(
        loan_id=loan[0]["id"], stage="installment_payment_failed", kind="rule",
        parsed={"event_type": event_type, "stream_payment_id": payment_id,
                "subscription_id": subscription_id},
    )
    return {"ok": True, "event_type": event_type, "loan_id": loan[0]["id"]}


def _handle_subscription_status(sb, subscription_id: str | None, new_status: str) -> dict:
    if not subscription_id:
        return {"ok": False, "reason": "no_subscription_id"}
    upd = sb.table("loans").update({"stream_subscription_status": new_status}) \
        .eq("stream_subscription_id", subscription_id).execute()
    return {"ok": True, "updated": len(upd.data or []), "status": new_status}


# ---------- resolver --------------------------------------------------------

async def _resolve_subscription_context(stream, event_type: str, body: dict, data: dict
                                        ) -> tuple[str | None, str | None, str | None]:
    """Given a Stream webhook body, figure out (subscription_id, invoice_id, payment_id).

    Prefer inline data → fall back to fetching the invoice/payment entity
    from Stream's API using entity_url.
    """
    invoice = data.get("invoice") or {}
    payment = data.get("payment") or {}
    invoice_id = invoice.get("id")
    payment_id = payment.get("id")
    subscription_id = data.get("subscription_id") or invoice.get("subscription_id")

    entity_id = body.get("entity_id")
    entity_type = str(body.get("entity_type") or "").upper()

    if not subscription_id and invoice_id and stream.is_live:
        try:
            inv = await stream.get_invoice(invoice_id)
            subscription_id = inv.get("subscription_id") or (inv.get("subscription") or {}).get("id")
        except StreamAPIError as e:
            log.warning("invoice lookup failed", extra={"invoice_id": invoice_id, "err": str(e)[:200]})

    if not subscription_id and entity_type == "PAYMENT" and entity_id and stream.is_live:
        try:
            p = await stream.get_payment(entity_id)
            payment_id = payment_id or p.get("id")
            inv = p.get("invoice") or {}
            invoice_id = invoice_id or inv.get("id")
            subscription_id = p.get("subscription_id") or inv.get("subscription_id")
        except StreamAPIError as e:
            log.warning("payment lookup failed", extra={"payment_id": entity_id, "err": str(e)[:200]})

    if not subscription_id and entity_type == "SUBSCRIPTION" and entity_id:
        subscription_id = entity_id

    return subscription_id, invoice_id, payment_id


# ---------- util ------------------------------------------------------------

def _safe_amount(data: dict, *, default: float) -> float:
    for key in ("amount_sar", "amount", "total_amount", "paid_amount"):
        v = data.get(key)
        if v is None: continue
        try: return float(v)
        except (TypeError, ValueError): continue
    pay = data.get("payment") or {}
    for key in ("amount", "amount_sar", "total_amount"):
        v = pay.get(key)
        if v is None: continue
        try: return float(v)
        except (TypeError, ValueError): continue
    inv = data.get("invoice") or {}
    for key in ("total_amount", "amount", "home_currency_amount"):
        v = inv.get(key)
        if v is None: continue
        try: return float(v)
        except (TypeError, ValueError): continue
    return default


def _extract_payment_method(data: dict) -> str | None:
    pay = data.get("payment") or {}
    return pay.get("payment_method") or data.get("payment_method")


# ---------- admin: regenerate link (legacy) ---------------------------------

@router.post("/loans/{loan_id}/install-schedule")
async def install_schedule_endpoint(loan_id: str) -> dict:
    """Install (or re-install) the repayment schedule + Stream subscription
    for an approved loan. Safe to call multiple times: `install_schedule_for_loan`
    short-circuits when installments already exist for the loan.

    Use cases:
      - Admin manually approves a `manual_review` loan (expert.synthesize
        isn't re-triggered, so installments aren't auto-created).
      - Recovering loans approved before the schedule-install bug fix landed.
      - Retrying a failed Stream subscription create (the local installments
        will already be in place; the Stream consumer/product/subscription
        chain is re-attempted idempotently).
    """
    sb = get_client()
    loan = sb.table("loans").select("*").eq("id", loan_id).maybe_single().execute().data
    if not loan:
        raise HTTPException(status_code=404, detail="loan not found")
    if loan.get("status") != "approved":
        raise HTTPException(
            status_code=409,
            detail=f"loan status is {loan.get('status')!r}; must be 'approved' to install schedule",
        )
    if not loan.get("approved_amount"):
        raise HTTPException(status_code=422, detail="loan has no approved_amount")

    from ..payments import install_schedule_for_loan  # local import to avoid cycle
    try:
        result = await install_schedule_for_loan(loan_id, loan)
    except Exception as e:  # noqa: BLE001
        log.exception("install_schedule_for_loan failed", extra={"loan_id": loan_id})
        write_event(
            loan_id=loan_id, stage="schedule_install_endpoint_failed", kind="rule",
            parsed={"error": str(e)[:500]},
        )
        raise HTTPException(status_code=500, detail=f"install failed: {str(e)[:300]}")

    return {
        "loan_id": loan_id,
        "installments_count": len(result.get("installments") or []),
        "stream": result.get("stream") or {},
    }


@router.post("/installments/{installment_id}/regenerate-link")
async def regenerate_link(installment_id: str):
    """Ad-hoc one-off payment link for a specific installment. Useful for
    missed-payment follow-ups outside the subscription flow."""
    sb = get_client()
    inst = sb.table("installments").select("*").eq("id", installment_id).single().execute().data
    if not inst:
        raise HTTPException(status_code=404, detail="installment not found")
    if inst["status"] == "paid":
        raise HTTPException(status_code=409, detail="installment already paid")

    # The subscription-based flow doesn't create per-installment links, but
    # admins sometimes want one to send manually. For now we return 501 and
    # rely on Stream's dashboard to re-notify; a follow-up PR can add an
    # endpoint that POSTs /api/v2/payment_links with an ad-hoc product.
    raise HTTPException(
        status_code=501,
        detail="regenerate-link not supported in subscription mode; trigger from Stream dashboard",
    )


# ---------- helpers copied from previous revision ---------------------------

def _bump_amount_paid(sb, loan_id: str, amount: float) -> None:
    current = sb.table("loans").select("amount_paid").eq("id", loan_id).single().execute().data
    new_total = float(current.get("amount_paid") or 0) + float(amount)
    sb.table("loans").update({"amount_paid": new_total}).eq("id", loan_id).execute()


async def _send_receipt(sb, inst: dict, amount: float) -> None:
    loan = sb.table("loans").select("id, merchant_id").eq("id", inst["loan_id"]).single().execute().data
    if not loan:
        return
    merchant = sb.table("merchants").select("user_id, business_name") \
        .eq("id", loan["merchant_id"]).single().execute().data
    if not merchant:
        return
    import httpx
    from ..config import CONFIG
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{CONFIG.supabase_url}/auth/v1/admin/users/{merchant['user_id']}",
            headers={"apikey": CONFIG.supabase_service_key,
                     "Authorization": f"Bearer {CONFIG.supabase_service_key}"},
        )
        if r.status_code >= 300:
            return
        email = r.json().get("email")
    if email:
        await send_payment_receipt_email(
            email, inst["loan_id"], inst["installment_number"], amount,
            merchant_name=merchant.get("business_name"),
        )

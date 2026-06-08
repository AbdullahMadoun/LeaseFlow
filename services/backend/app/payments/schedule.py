"""Repayment schedule generation + Stream subscription installation.

On loan approval:
  1. compute_schedule   — produces N installment dicts (local math)
  2. install_schedule_for_loan — persists installments + creates the
     Stream Consumer/Product/Subscription chain so Stream bills the
     merchant on cadence.

Cadence math (local, used for due_date calc and sanity display):
  monthly   : N = repayment_months                 due dates spaced by 30 days
  biweekly  : N = repayment_months * 2             spaced by 14 days
  weekly    : N = repayment_months * 4             spaced by  7 days
  daily     : N = repayment_months * 30            spaced by  1 day

Stream's subscription engine only supports WEEK / MONTH / YEAR (no DAY),
so `daily` loans fall back to a weekly subscription with weekly_amount =
amount_sar * 7 — the local installments table still reflects the daily
schedule for admin-side reporting.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from ..config import CONFIG
from ..supabase_client import get_client
from ..tracing import write_event
from .stream import (
    StreamAPIError,
    StreamConsumer,
    StreamProduct,
    StreamSubscription,
    get_stream_client,
)

log = logging.getLogger(__name__)

Frequency = Literal["daily", "weekly", "biweekly", "monthly"]

DAYS_PER_STEP: dict[Frequency, int] = {
    "daily": 1, "weekly": 7, "biweekly": 14, "monthly": 30,
}
STEPS_PER_MONTH: dict[Frequency, int] = {
    "daily": 30, "weekly": 4, "biweekly": 2, "monthly": 1,
}


# ---- local schedule math ----------------------------------------------------

def compute_schedule(
    *,
    approved_amount_sar: float,
    profit_rate: float,
    repayment_months: int,
    frequency: Frequency = "monthly",
    start_date: date | None = None,
) -> list[dict]:
    total_due = round(approved_amount_sar * (1 + profit_rate), 2)
    steps = max(1, repayment_months * STEPS_PER_MONTH[frequency])
    step_days = DAYS_PER_STEP[frequency]
    per = round(total_due / steps, 2)
    start = start_date or date.today()

    amounts = [per] * steps
    amounts[-1] = round(total_due - per * (steps - 1), 2)

    return [
        {
            "installment_number": i + 1,
            "due_date": (start + timedelta(days=step_days * (i + 1))).isoformat(),
            "amount_sar": amounts[i],
        }
        for i in range(steps)
    ]


# ---- frequency → Stream interval -------------------------------------------

def map_frequency_to_stream(
    frequency: Frequency, *, per_installment_amount: float
) -> tuple[str, int, float, int]:
    """Return (recurring_interval, interval_count, stream_amount, stream_cycles_per_local_installment).

    Stream supports WEEK, MONTH, YEAR. `daily` gets rolled up into weekly
    subscriptions (7× the per-day installment amount) since Stream can't
    bill daily. In that case `stream_cycles_per_local_installment=1/7`
    conceptually, but we return 1 since we still create one Stream cycle
    per Stream billing event — the local installments/Stream cycles mapping
    is 7-to-1 for daily loans (7 local rows marked paid per Stream cycle).
    """
    if frequency == "monthly":
        return "MONTH", 1, per_installment_amount, 1
    if frequency == "weekly":
        return "WEEK", 1, per_installment_amount, 1
    if frequency == "biweekly":
        return "WEEK", 2, per_installment_amount, 1
    if frequency == "daily":
        return "WEEK", 1, round(per_installment_amount * 7, 2), 7
    raise ValueError(f"unknown repayment_frequency: {frequency!r}")


# ---- main entry point ------------------------------------------------------

async def install_schedule_for_loan(loan_id: str, loan: dict) -> dict:
    """Idempotent. Creates installments, Stream consumer/product/subscription.

    Returns a summary dict {installments: [...], stream: {...}}.
    """
    sb = get_client()

    existing = sb.table("installments").select("id").eq("loan_id", loan_id).execute().data or []
    if existing:
        log.info("schedule already installed, skipping", extra={"loan_id": loan_id, "count": len(existing)})
        return {"installments": existing, "stream": {"skipped": "already_installed"}}

    approved = float(loan.get("approved_amount") or 0)
    if approved <= 0:
        log.warning("no approved_amount, skipping schedule", extra={"loan_id": loan_id})
        return {"installments": [], "stream": {"skipped": "no_amount"}}

    frequency: Frequency = loan.get("repayment_frequency") or "monthly"
    schedule = compute_schedule(
        approved_amount_sar=approved,
        profit_rate=float(loan.get("profit_rate") or 0.15),
        repayment_months=int(loan.get("repayment_months") or 12),
        frequency=frequency,
    )

    # Local installments first — durable source of truth regardless of Stream.
    base_rows = [
        {
            "loan_id": loan_id,
            "installment_number": r["installment_number"],
            "due_date": r["due_date"],
            "amount_sar": r["amount_sar"],
        }
        for r in schedule
    ]
    inserted = sb.table("installments").insert(base_rows).execute().data or []

    stream_summary = await _install_stream_subscription(
        sb=sb, loan_id=loan_id, loan=loan,
        per_installment_amount=float(schedule[0]["amount_sar"]),
        total_cycles=len(schedule),
        frequency=frequency,
        first_due_iso=str(schedule[0]["due_date"]),
    )

    write_event(
        loan_id=loan_id, stage="repayment_schedule_installed", kind="rule",
        parsed={
            "installment_count": len(inserted),
            "frequency": frequency,
            "first_due_date": schedule[0]["due_date"],
            "last_due_date": schedule[-1]["due_date"],
            "total_due_sar": sum(r["amount_sar"] for r in schedule),
            "stream": stream_summary,
        },
    )
    return {"installments": inserted, "stream": stream_summary}


# ---- Stream wiring ---------------------------------------------------------

async def _install_stream_subscription(
    *,
    sb,
    loan_id: str,
    loan: dict,
    per_installment_amount: float,
    total_cycles: int,
    frequency: Frequency,
    first_due_iso: str,
) -> dict:
    """Consumer → Product → Subscription. Each step is best-effort: a
    failure is recorded on the loan and the install continues — the admin
    can retry later. Merchants with a pre-existing Stream consumer ID are
    reused.

    `first_due_iso` is a YYYY-MM-DD date string representing when the first
    installment is due locally. We use it as the Stream `period_start` so
    Stream's first charge lands on the same day as our first installment
    row — for lease-to-own that's roughly 30 days after approval, giving
    the merchant a proper grace period before the first debit.
    """
    stream = get_stream_client()
    if not stream.is_live:
        log.info("stream not configured, skipping subscription install", extra={"loan_id": loan_id})
        return {"skipped": "stream_not_configured"}

    merchant = sb.table("merchants").select("*").eq("id", loan["merchant_id"]).single().execute().data
    if not merchant:
        log.warning("merchant not found for stream install", extra={"loan_id": loan_id})
        return {"error": "merchant_not_found"}

    # 1. Consumer -----------------------------------------------------------
    try:
        consumer = await _upsert_consumer(sb=sb, stream=stream, merchant=merchant)
    except StreamAPIError as e:
        log.exception("stream consumer upsert failed", extra={"loan_id": loan_id})
        return {"stage": "consumer", "error": str(e)[:300]}

    # 2. Product ------------------------------------------------------------
    interval, interval_count, stream_amount, local_per_cycle = map_frequency_to_stream(
        frequency, per_installment_amount=per_installment_amount,
    )
    stream_cycles = max(1, total_cycles // max(1, local_per_cycle))
    product_name = f"LeaseFlow loan {loan_id[:8]} · {frequency} × {total_cycles}"
    try:
        product = await stream.create_recurring_product(
            name=product_name,
            amount_sar=stream_amount,
            recurring_interval=interval,
            recurring_interval_count=interval_count,
            description=(loan.get("item_description") or "")[:200] or None,
        )
    except StreamAPIError as e:
        log.exception("stream product create failed", extra={"loan_id": loan_id})
        sb.table("loans").update({"stream_subscription_status": f"product_error: {str(e)[:200]}"}) \
            .eq("id", loan_id).execute()
        return {"stage": "product", "error": str(e)[:300],
                "stream_consumer_id": consumer.id}

    sb.table("loans").update({"stream_product_id": product.id}).eq("id", loan_id).execute()

    # 3. Subscription -------------------------------------------------------
    # Stream requires RFC-3339 with timezone marker.
    # Align Stream's first cycle with our first installment so the merchant
    # gets the full grace period before the first debit (BNPL semantics).
    # Fallback to +30d if parsing the due_date string fails for any reason.
    try:
        first_due_dt = datetime.fromisoformat(first_due_iso).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        first_due_dt = datetime.now(timezone.utc) + timedelta(days=30)
    # Never anchor to the past — Stream rejects past period_start values.
    if first_due_dt < datetime.now(timezone.utc):
        first_due_dt = datetime.now(timezone.utc) + timedelta(days=1)
    period_start = first_due_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        sub = await stream.create_subscription(
            product_id=product.id,
            consumer_id=consumer.id,
            period_start=period_start,
            until_cycle_number=stream_cycles,
            description=f"LeaseFlow loan {loan_id}",
            notify_consumer=True,
        )
    except StreamAPIError as e:
        log.exception("stream subscription create failed", extra={"loan_id": loan_id})
        sb.table("loans").update({"stream_subscription_status": f"sub_error: {str(e)[:200]}"}) \
            .eq("id", loan_id).execute()
        return {"stage": "subscription", "error": str(e)[:300],
                "stream_consumer_id": consumer.id,
                "stream_product_id": product.id}

    sb.table("loans").update({
        "stream_subscription_id": sub.id,
        "stream_subscription_status": sub.status,
    }).eq("id", loan_id).execute()

    # Eagerly seed the first installment's pay-now link from the subscription's
    # opening invoice so the merchant Payments page has a button to click
    # immediately — before any INVOICE_CREATED webhook fires.
    if sub.latest_invoice_id:
        try:
            invoice = await stream.get_invoice(sub.latest_invoice_id)
            first = sb.table("installments").select("id") \
                .eq("loan_id", loan_id).eq("status", "pending") \
                .order("installment_number").limit(1).execute().data
            if first:
                sb.table("installments").update({
                    "stream_invoice_id": sub.latest_invoice_id,
                    "stream_payment_link_id": sub.latest_invoice_id,
                    "stream_payment_url": invoice.get("url"),
                }).eq("id", first[0]["id"]).execute()
        except Exception as e:  # noqa: BLE001
            log.warning("first-invoice link seed failed", extra={
                "loan_id": loan_id, "err": str(e)[:200]})

    log.info("stream subscription installed", extra={
        "loan_id": loan_id, "subscription_id": sub.id, "product_id": product.id,
        "consumer_id": consumer.id, "cycles": stream_cycles, "interval": interval,
    })
    return {
        "stream_consumer_id": consumer.id,
        "stream_product_id": product.id,
        "stream_subscription_id": sub.id,
        "status": sub.status,
        "cycles": stream_cycles,
        "interval": interval,
        "interval_count": interval_count,
        "amount_per_cycle_sar": stream_amount,
    }


async def _upsert_consumer(*, sb, stream, merchant: dict) -> StreamConsumer:
    """Return an existing Stream consumer for this merchant, or create one.
    Stores `stream_consumer_id` on the merchants row once known."""
    existing_id = merchant.get("stream_consumer_id")
    if existing_id:
        return StreamConsumer(id=existing_id, name=merchant.get("business_name", ""),
                              external_id=merchant["id"])

    # Look up merchant's auth email for the consumer record (best-effort).
    email = await _lookup_merchant_email(sb, merchant["user_id"])
    # In sandbox mode Stream enforces phone == org-owner phone; let the
    # STREAM_SANDBOX_PHONE override win when set.
    phone = CONFIG.stream_sandbox_phone or merchant.get("phone")
    consumer = await stream.get_or_create_consumer(
        name=merchant.get("business_name") or "LeaseFlow merchant",
        external_id=merchant["id"],
        phone_number=phone,
        email=email,
        commercial_registration=merchant.get("cr_number"),
        consumer_type=CONFIG.stream_consumer_type,
    )
    sb.table("merchants").update({"stream_consumer_id": consumer.id}) \
        .eq("id", merchant["id"]).execute()
    return consumer


async def _lookup_merchant_email(sb, user_id: str) -> str | None:
    """Hit Supabase Auth admin API to grab the merchant's email (best-effort)."""
    if not user_id:
        return None
    try:
        import httpx
        from ..config import CONFIG as _C
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(
                f"{_C.supabase_url}/auth/v1/admin/users/{user_id}",
                headers={"apikey": _C.supabase_service_key,
                         "Authorization": f"Bearer {_C.supabase_service_key}"},
            )
            if r.status_code >= 300:
                return None
            return r.json().get("email")
    except Exception:  # noqa: BLE001
        return None

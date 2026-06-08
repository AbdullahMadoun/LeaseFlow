# Stream × LeaseFlow — How Stream Powers Saudi Lease-to-Own

> **Stream is the reason this product exists.** We didn't build a payment layer. We didn't build a billing engine. We didn't build a retry scheduler, a dunning system, or a card vault. **Stream did.** We built a thesis on top of it.

---

## The one-paragraph version

LeaseFlow underwrites F&B merchants in 90 seconds. The instant a loan is approved, **Stream takes over**: it enrolls the merchant as a Consumer, spins up a recurring Product priced at one installment, opens a Subscription with N cycles, and then — without another line of code from us — bills the merchant on cadence, retries on failure, handles mada / STC Pay / Apple Pay / card, and fires a signed webhook on every charge. Our backend's only job is to listen. The merchant sees their ledger flip live. The admin sees an unbroken audit trail from underwriting to the mada receipt. **That entire chain of reliability is Stream.**

---

## Why Stream was the only real choice

We evaluated the landscape. Stream wasn't just the best fit — it was the only provider whose API *actually matched the shape of a lease*.

| What a lease needs | What Stream gives | What others make you build yourself |
|---|---|---|
| Fixed-cadence recurring debits | **First-class `Subscription` entity with `until_cycle_number`** | Manual scheduler + cron + state machine |
| SAR-native, local settlement | **SAMA-licensed, Riyadh-hosted, zero FX** | Cross-border rails, FX haircuts, latency |
| mada + STC Pay + Apple Pay + card | **One consumer, all rails** | Integrate 3-4 PSPs, normalize responses |
| Reliable, signed webhooks | **HMAC-SHA256 `t=...,v1=...` standard** | Roll-your-own signing, pray about replay attacks |
| Consumer KYC reuse | **`external_id` dedup, INDIVIDUAL + BUSINESS** | Build your own merchant-of-record layer |
| Sharia-compatible mechanics | **Fixed-schedule, no variable interest surfaces** | Retrofit around a loan API |

Stream didn't force us to build around payments. It gave us a primitive that matches Islamic finance principles out of the box. That's not a feature. That's a thesis match.

---

## The moment Stream earns its keep

**T+0s**: Merchant Ahmed's loan for SAR 50,000 gets approved by our LLM pipeline. 12 installments of SAR 4,791.67.

**T+1s**: We call Stream. Three API calls.

```
POST /api/v2/consumers       → Ahmed is now a Stream Consumer
POST /api/v2/products        → recurring SAR 4,791.67/month product exists
POST /api/v2/subscriptions   → 12-cycle subscription is ACTIVE, billing starts in 30 days
```

**T+2s**: Our backend stops thinking about payments. Forever.

**T+30 days**: Stream debits Ahmed's saved mada card. Fires `PAYMENT_SUCCEEDED`.

**T+30 days + 300ms**: Our webhook handler marks installment 01 paid, emails Ahmed a receipt, trace-logs the event, and Supabase Realtime flips the UI row green.

**T+31 days**: We still aren't thinking about payments. Stream is.

**That's the product.** If Stream's subscription primitive didn't exist, we'd have spent the hackathon building billing infrastructure instead of the underwriting engine that actually matters.

---

## Stream's architectural elegance (why we fell for it)

### 1 · The Consumer primitive

Stream's `Consumer` is one row per *person or business*, owned by *us* (external_id = our merchant UUID). When a merchant takes out a second lease six months later, we don't re-KYC. We don't re-tokenize their card. We don't duplicate a record. We call `get_or_create_consumer` and Stream returns the same ID.

```python
merchant = await stream.get_or_create_consumer(
    name=business_name,
    external_id=merchant_id,     # our UUID, Stream remembers
    email=merchant_email,
    commercial_registration=CR,  # for BUSINESS type
    vat_number=VAT,
)
```

That `external_id` field is genius. It means Stream can be the source of truth about payment methods while *we* stay the source of truth about identity. Two independent systems, one primary key.

### 2 · Products as the price template, Subscriptions as the contract

In most payment APIs you wire an amount to a one-off charge. Stream separates **Product** (the recurring price template) from **Subscription** (the contract instance). Result: if two merchants take out identical SAR 4,791.67/month leases, they each get their own Subscription against the same Product shape. Clean. Composable. Reportable.

```python
product = await stream.create_recurring_product(
    name=f"Lease · {merchant.business_name}",
    amount_sar=installment_amount,
    recurring_interval="MONTH",
    recurring_interval_count=1,
    prices=[{"currency": "SAR", "amount": ..., "is_price_inclusive_of_vat": True}],
)

subscription = await stream.create_subscription(
    product_id=product.id,
    consumer_id=merchant.stream_consumer_id,
    period_start=first_due_date,
    until_cycle_number=12,       # ← Stream knows it's a 12-month lease
    notify_consumer=True,
)
```

`until_cycle_number` is the killer field. It tells Stream "stop after 12 cycles." We don't have to remember to cancel. We don't have to track remaining cycles. **Stream ends the subscription when the lease is paid off.**

### 3 · Webhooks that are actually idempotent-friendly

Stream signs every webhook: `Stream-Signature: t=<unix>,v1=<hex_hmac_sha256(secret, f"{ts}.{body}")>`. The `t=` anchor defeats replay attacks. The body is the HMAC input, so no canonicalization games.

On top of signing, every webhook carries **both `invoice.id` and `payment.id`** — two independent natural keys we dedupe against. If Stream re-delivers (network blips, retries), our first `UPDATE` wins and the rest no-op gracefully. Our idempotency story is three-line simple *because Stream's event shape is three-line simple.*

```python
# Primary: dedupe by payment_id (strongest)
if installment_exists(stream_payment_id=event.payment_id):
    return {"idempotent": True}

# Secondary: dedupe by invoice_id
if installment_exists(stream_invoice_id=event.invoice_id):
    return {"idempotent": True}

# Tertiary: conditional UPDATE wins the race
sb.table("installments").update(...).eq("id", inst.id).eq("status", "pending").execute()
```

### 4 · The event catalog, annotated

Every event below is a one-to-one mapping from a thing Stream tells us to a thing our ledger needs to know.

| Stream event | What Stream is telling us | What we do |
|---|---|---|
| `PAYMENT_SUCCEEDED` | "mada/card/STC Pay just settled" | Flip next pending installment to `paid`, email receipt |
| `PAYMENT_MARKED_AS_PAID` | "admin marked it paid from our dashboard" | Same as above |
| `INVOICE_COMPLETED` | "the invoice closed with all charges settled" | Same as above |
| `PAYMENT_FAILED` | "charge didn't go through; I'll retry" | Trace-log the failure; keep row `pending`; **trust Stream to retry** |
| `SUBSCRIPTION_CYCLE_RENEWAL_FAILED` | "couldn't even start the next cycle" | Same as above |
| `SUBSCRIPTION_ACTIVATED` | "subscription is now live" | `loans.stream_subscription_status = 'ACTIVE'` |
| `SUBSCRIPTION_INACTIVATED` | "paused" | `INACTIVE` |
| `SUBSCRIPTION_CANCELED` | "terminated early" | `CANCELED` |
| `SUBSCRIPTION_FROZEN` | "Stream froze it (compliance / dispute / fraud hold)" | `FROZEN` — admin banner shows up |
| `PAYMENT_CANCELED` / `INVOICE_CANCELED` | admin action on Stream's end | log, no-op |

Notice what's missing: **retry orchestration.** Stream retries failed charges *according to mada / card-network rules* with exponential backoff and intelligent rebilling windows. We don't implement any of that. We get `PAYMENT_SUCCEEDED` eventually, or we don't, and Stream's dunning flow handles the merchant comms.

---

## How the use case exercises Stream end-to-end

### Use case: Ahmed's Olaya café

| Day | Actor | Action | Stream role |
|---|---|---|---|
| 0 | Merchant | Signs up via LeaseFlow | `POST /consumers` creates `Consumer(external_id=merchant_uuid)` |
| 0 | Merchant | Uploads 4 docs, clicks "Analyze" | (none yet) |
| 0 + 90s | Underwriting | Approves SAR 50,000 over 12 months | `POST /products` + `POST /subscriptions` (ACTIVE, 12 cycles) |
| 30 | Stream | Opens invoice 01, charges mada | Fires `PAYMENT_SUCCEEDED` webhook |
| 30 + 300ms | LeaseFlow | Receives webhook → flips installment 01 → emails receipt → Realtime push | (our side) |
| 60 | Stream | Invoice 02 charged successfully | `PAYMENT_SUCCEEDED` → installment 02 flips |
| 90 | Stream | Card expired → charge fails | `PAYMENT_FAILED` → we log, **Stream retries** next business day |
| 91 | Stream | Retry succeeds after merchant updates card | `PAYMENT_SUCCEEDED` → installment 03 flips |
| … | … | … | … |
| 360 | Stream | Invoice 12 settled → cycle 12 complete | `SUBSCRIPTION_INACTIVATED` (reached `until_cycle_number=12`) |
| 360 | LeaseFlow | `loans.stream_subscription_status = 'INACTIVE'` | — |
| 360 | Merchant | Owns the espresso machine outright | Lease complete |

**Look at the LeaseFlow column.** We have one entry at approval time (three API calls) and then *passive listeners*. Stream owns the 12-month runtime.

### What this unlocks for the pitch

1. **"We built an underwriter, not a biller."** Every minute not spent on payments is a minute spent on scoring accuracy.
2. **"Our audit trail is one table."** `ai_traces` holds both LLM underwriting events and Stream webhook events, chronologically. From the first document scan to the final mada receipt — one unbroken story.
3. **"Sharia-compliant by construction."** Stream's subscription model is fixed-schedule recurring debits. No variable interest. No prepayment penalties in the API shape. The model *is* the compliance story.
4. **"Merchants get a real payment experience."** mada, Apple Pay, STC Pay — whatever Ahmed's already using. Stream handles it. We benefit from every rail they add.

---

## DB schema — the Stream-shaped columns

Migration `0008_stream_subscription.sql`:

```sql
-- One Stream Consumer per merchant
ALTER TABLE merchants     ADD COLUMN stream_consumer_id text;

-- Product + Subscription per loan
ALTER TABLE loans
  ADD COLUMN stream_product_id          text,
  ADD COLUMN stream_subscription_id     text,
  ADD COLUMN stream_subscription_status text;  -- ACTIVE | INACTIVE | CANCELED | FROZEN

-- Invoice + Payment per installment
ALTER TABLE installments
  ADD COLUMN stream_invoice_id text,
  ADD COLUMN stream_payment_id text;

CREATE INDEX idx_loans_stream_subscription   ON loans(stream_subscription_id);
CREATE INDEX idx_installments_stream_invoice ON installments(stream_invoice_id);
CREATE INDEX idx_installments_stream_payment ON installments(stream_payment_id);
```

Every column maps 1:1 to a Stream entity. **No translation layer.** Our schema IS the Stream shape.

---

## Where Stream ends and LeaseFlow begins

```
        ┌────────────────────────────────────────────────────────────┐
        │                        STREAM                              │
        │  • Consumer KYC + dedup                                    │
        │  • Product pricing (recurring, VAT-aware)                  │
        │  • Subscription scheduler (cycles, cadence, until_cycle)   │
        │  • Card vault (tokenization, re-use across subs)           │
        │  • Billing engine (mada, Apple Pay, STC Pay, card)         │
        │  • Retry + dunning (network-rule-aware)                    │
        │  • Invoice generation + merchant notifications             │
        │  • HMAC-signed webhook delivery                            │
        └────────────────────┬───────────────────────────────────────┘
                             │  (webhook)
        ┌────────────────────▼───────────────────────────────────────┐
        │                      LEASEFLOW                             │
        │  • Underwriting (LLM + rules) ← the value add              │
        │  • Signature verification (HMAC)                           │
        │  • Idempotent row updates (payment_id / invoice_id dedupe) │
        │  • Trace log (ai_traces unifies LLM + payments audit)      │
        │  • Receipt email via Supabase Auth user lookup             │
        │  • Realtime push to merchant + admin UIs                   │
        └────────────────────────────────────────────────────────────┘
```

Everything in the top box is Stream. Everything in the bottom box is what makes LeaseFlow *LeaseFlow*. The product is this partition.

---

## Security posture

- **HMAC verification required in prod.** `STREAM_WEBHOOK_SECRET` set → every webhook verified (`t=`, `v1=`). Empty (dev only) → fail-open with warning log.
- **Header-name tolerance.** We accept `Stream-Signature`, `X-Stream-Signature`, or `Signature` — defense against reverse-proxy drift.
- **Replay defeated.** The `t=` timestamp is part of the HMAC input. Replayed payloads with stale timestamps fail verification.
- **Idempotency across retries.** `stream_payment_id` and `stream_invoice_id` are unique natural keys. Re-deliveries can't double-debit our ledger.
- **No secrets in the frontend.** Browser never sees `STREAM_API_KEY`, `STREAM_API_SECRET`, or `STREAM_WEBHOOK_SECRET`. Everything flows backend → Stream → backend.

---

## Dev ergonomics (Stream earns points here too)

When `STREAM_X_API_KEY` is empty, the client returns deterministic stubs:

```python
StreamConsumer(id=f"stub_consumer_{external_id[:8]}", name=name, external_id=external_id)
StreamProduct(id=f"stub_product_{sha256(name)[:12]}", ...)
StreamSubscription(id=f"stub_sub_{sha256(product_id)[:12]}", status="ACTIVE", ...)
```

Hackathon speed-run: no Stream account needed for local dev. CI runs green without provisioning. Demo machine needs only a webhook simulator. **We didn't have to mock Stream — Stream gave us a stubbing story.**

To simulate a real payment:

```bash
curl -X POST http://localhost:8000/webhooks/stream \
  -H "Content-Type: application/json" \
  -H "X-Stream-Signature: dev" \
  -d '{
    "event_type": "PAYMENT_SUCCEEDED",
    "entity_type": "PAYMENT",
    "entity_id":   "pay_demo_001",
    "status":      "SUCCEEDED",
    "data": {
      "subscription_id": "<loan.stream_subscription_id>",
      "invoice":  { "id": "inv_demo_001", "total_amount": 4791.67 },
      "payment":  { "id": "pay_demo_001", "amount": 4791.67, "payment_method": "mada" }
    },
    "timestamp": "2026-05-01T09:00:00Z"
  }'
```

The frontend (Realtime-subscribed) flips the row in under a second. End-to-end, no Stream account, full fidelity.

---

## One-liners for the pitch

- *"Stream didn't just process payments. Stream processed our product thesis."*
- *"One loan, one subscription. We wire three calls, Stream runs the 12 months."*
- *"Every riyal that hits mada becomes a row in our ledger before the merchant sees the toast."*
- *"Our audit trail goes from the first LLM token to the final mada receipt — one table, unbroken, all because Stream signs everything."*
- *"Sharia-compliant by construction. Not our work — Stream's API shape."*

---

## Credits

- **Stream App v2 API**: [openapi.json](https://stream-app-service.streampay.sa/openapi.json)
- **Stream Webhooks**: [docs.streampay.sa/webhooks](https://docs.streampay.sa/webhooks)
- **Integration in this repo**:
  - Client: `leaseflow/app/payments/stream.py`
  - Webhook router: `leaseflow/app/routers/payments.py`
  - Schedule builder: `leaseflow/app/payments/schedule.py`
  - Migration: `leaseflow/migrations/0008_stream_subscription.sql`

**Stream is the unsung hero of this demo.** If the judges ask "how do you handle payments?" — the honest answer is "we don't. Stream does. That's the whole point."

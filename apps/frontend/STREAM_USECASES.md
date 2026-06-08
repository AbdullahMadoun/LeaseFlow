# Stream × LeaseFlow — What We Actually Use Stream For

Not an API reference. The **product** story: what Stream *does* for a real merchant, a real admin, a real auditor.

---

## The short answer

Stream is LeaseFlow's **payments nervous system**. Everything about money — who pays, when, how, what happens if it fails, what the receipt says, how admins pause it — lives in Stream. LeaseFlow underwrites. Stream does the rest.

After we approve Ahmed's SAR 50,000 lease, our backend makes three calls to Stream and then goes silent for 12 months. Stream runs the repayment. We just listen.

---

## The 10 product moments Stream makes possible

### 1 · "Enroll once. Lease forever."

**The moment**: Ahmed's first lease closes. Six months later, his cousin-branch manager wants a second espresso machine.
**Without Stream**: re-upload ID, re-enter mada card, re-verify business, re-sign authorization.
**With Stream**: Ahmed opens LeaseFlow, sees "Welcome back — same card on file?", taps yes, signs. One screen.

Stream already knows him via `external_id = merchant_uuid`. His card vault, his KYC, his contact preferences — all persisted on Stream's side. Second lease = second subscription against the same Consumer. We didn't build that relationship. Stream did.

---

### 2 · "Set once. Billed for 12 months."

**The moment**: We approve the lease. Click, approve, done.
**What happens next**: For the next 360 days, LeaseFlow doesn't think about payments. At all.

Stream bills Ahmed on day 30, day 60, day 90… We don't run a scheduler. We don't have a cron job. We don't worry about Daylight Savings, Ramadan, or Friday/Saturday settlement. Stream's `until_cycle_number: 12` field is the entire contract. When cycle 12 settles, Stream closes the subscription automatically. No cleanup on our end.

*"Three API calls at approval time. Silence for a year. That's the product."*

---

### 3 · "Pay however you pay already."

**The moment**: Ahmed prefers mada. His admin chef uses STC Pay. The delivery service uses Apple Pay. The corporate QSR uses a credit card.
**The product experience**: Stream's checkout shows every local rail. The merchant picks whatever's in their phone already. We never specify.

This isn't one Stream feature — it's **every payment rail in the Kingdom** behind one API. Every time Stream adds a new rail (SADAD? Tabby? BNPL?), LeaseFlow inherits it the same day. No integration. No migration. No release.

---

### 4 · "When a card fails, the product doesn't."

**The moment**: Ahmed's mada card expires mid-lease.
**Without Stream**: Our backend panics. We send an angry SMS. His installment goes delinquent. His credit gets dinged. Our admin gets paged.
**With Stream**: Stream retries on day 2, 5, 10 using mada network rules. It emails Ahmed a "please update your card" link. Ahmed updates it on Stream's hosted page. Stream re-attempts the charge. Success on day 11.

All LeaseFlow sees: a `PAYMENT_FAILED` log, then a `PAYMENT_SUCCEEDED` eleven days later. Ahmed's lease never "went bad". Stream's dunning flow — **regulated, Arabic-localized, SAMA-compliant** — handled the hard part.

---

### 5 · "The ledger flips live."

**The moment**: Stream settles cycle 01. Ahmed is walking into his café, phone in his pocket.
**300ms later**: Ahmed's lease dashboard already shows a green ✓ PAID chip on installment 01, even though he never touched his phone.

Webhook → backend marks row paid → Supabase Realtime pushes → UI row flips. This chain of custody — Stream → Supabase → browser — all fires in under a second. **The ledger isn't a report anyone generates. It's a reflection of Stream's truth, in real time.**

---

### 6 · "Pause for Ramadan. Resume for Shawwal."

**The moment**: Ahmed calls in — he's closing for 2 weeks during Ramadan, can he pause his lease?
**Without Stream**: We'd have to build a whole state-machine for frozen subscriptions. Rebill logic. Partial-month accounting.
**With Stream**: Admin hits "Freeze" in the dashboard. Stream's `SUBSCRIPTION_FROZEN` event updates `loans.stream_subscription_status`. No billing during the freeze. Admin unfreezes. Cycle resumes. All native.

Same for early payoffs, hardship deferrals, business closures. Stream's subscription states cover the real life of a café owner.

---

### 7 · "Every riyal has a paper trail."

**The moment**: An auditor — from SAMA, from the Sharia board, from accounting — asks to trace one installment.
**The answer**: One query joins our `installments` table to Stream's invoice_id and payment_id. We show: when the underwriting approved it, when Stream scheduled it, when it was billed, by what rail, what the mada ARN was, when it settled, when the receipt went out.

Every riyal has lineage. **Underwriting event → subscription creation → invoice → payment → receipt.** One unbroken chain. Because Stream's entity model maps 1:1 to ours, the audit isn't two systems reconciled — it's one story told twice.

---

### 8 · "Receipts, dunning, reminders — without a mail server."

**The moment**: Ahmed's installment settles. Ten seconds later his phone buzzes with a Stream receipt in Arabic, with the mada logo, with our branding.
**Behind the scenes**: we didn't build a transactional email system for payments. Stream owns the merchant communication for everything money-adjacent: receipts, failure reminders, card-update requests, end-of-lease summaries.

LeaseFlow sends the *underwriting* communications (congrats, your lease is approved!). Stream sends the *payment* communications (here's your receipt!). Clean handoff. The merchant experiences one product.

---

### 9 · "Admin has a real console, not a toy."

**The moment**: An admin needs to mark an installment paid manually (merchant paid in cash at the storefront during a network outage).
**Without Stream**: We'd have to build override logic, settlement logic, reconciliation logic.
**With Stream**: Admin marks it paid in Stream's dashboard. Stream fires `PAYMENT_MARKED_AS_PAID`. Our webhook handler treats it identically to a real charge. Ledger updates. Receipt sends. Lease advances.

Stream's dashboard isn't a backup to ours — it's a *second cockpit*. Admins have full operator control even when our UI is down for a deploy.

---

### 10 · "Sharia-compliant by API shape."

**The moment**: Islamic finance review asks "where's the variable-rate logic? Where's the prepayment penalty? Where's the interest amortization?"
**The answer**: There isn't any. The product is a fixed-schedule recurring debit of the same SAR amount for N cycles. Stream's `Subscription` primitive doesn't support variable rates in the first place. The model IS the compliance.

We didn't retrofit Sharia compliance onto a loan API. We built a lease on a primitive that's **structurally** lease-shaped: fixed amount × fixed cycles × fixed cadence × asset-backed. Stream's API is in that shape. So ours is too. So our Sharia story is "read the API spec."

---

## The partition

```
       STREAM OWNS                         LEASEFLOW OWNS
       ───────────                         ──────────────
  • Merchant KYC vault                 • Underwriting (LLM + rules)
  • Saved payment methods              • Approval decision
  • Recurring billing engine           • Audit trail (ai_traces)
  • mada / STC Pay / Apple Pay         • Installment lifecycle view
  • Retry + dunning logic              • Admin override tools
  • Invoice generation                 • Merchant UI (dashboard, ledger)
  • Receipt emails                     • Admin UI (pipeline, detail)
  • Cancellation + freeze              • Risk snapshot
  • Webhook signing + delivery         • Idempotent webhook handling
```

**Everything hard about money is on the Stream side.** LeaseFlow is an underwriter with a pretty ledger view.

---

## What LeaseFlow would have to build if Stream didn't exist

This is the list that justifies Stream's place in the stack. If Stream vanished tomorrow, our 7-day hackathon becomes a 7-month engineering project:

1. **PCI-DSS-compliant card vault** — months of infra + audit
2. **Direct mada integration** — SAMA licensing, bank-level regulatory review
3. **Direct STC Pay integration** — separate partnership, separate compliance
4. **Apple Pay merchant setup** — separate flow again
5. **Recurring billing scheduler** — with retry logic, backoff, jitter
6. **Dunning email infrastructure** — transactional, localized, compliant
7. **Receipt email templates** — branded, VAT-accurate, legally valid
8. **Webhook signing infrastructure** — for any future partners
9. **Settlement reconciliation** — matching bank statements to expected charges
10. **Chargeback / dispute handling** — the banking world's landmine
11. **Card-update flows** — when cards expire or get replaced
12. **Cancellation / refund flows** — pro-rata math, settlement reversals

**None of that is LeaseFlow's value.** LeaseFlow's value is deciding, in 90 seconds, whether Ahmed's café is creditworthy. Everything else is Stream.

*"We outsourced the 95% of fintech complexity that isn't our differentiator."*

---

## Why this matters for the pitch

When a judge asks *"how do you actually move money?"* — the answer isn't a technical walkthrough. It's a **sentence about philosophy**:

> "Stream moves the money. We underwrite. Because Stream's primitives match a lease's shape exactly, our integration is three API calls at approval time and a webhook listener. We built an underwriter, not a biller. That's the only reason we shipped a working system in a week."

That sentence is a thesis. It's why we chose Stream. It's why Stream chose Saudi. It's why the match works.

---

## One-line anchor per use case (for speaking on stage)

1. *Enroll once, lease forever.*
2. *Three calls at approval, silence for a year.*
3. *Every payment rail in the Kingdom, one API.*
4. *When a card fails, the product doesn't.*
5. *The ledger flips before the merchant's phone buzzes.*
6. *Pause for Ramadan. Resume for Shawwal.*
7. *Every riyal has a paper trail.*
8. *Receipts and dunning — without a mail server.*
9. *Admins get a second cockpit.*
10. *Sharia-compliant by API shape.*

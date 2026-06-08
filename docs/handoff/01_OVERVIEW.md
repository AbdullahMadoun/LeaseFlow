# 01 — Project Overview

## The product in one sentence

**LeaseFlow buys F&B equipment for Saudi merchants, then leases it back with a markup.**
A café owner wants a 50,000 SAR espresso machine → LeaseFlow pays the vendor →
merchant pays LeaseFlow back in 12 monthly installments at a 15% profit rate.

## Why this exists

Small F&B businesses in KSA (coffee shops, restaurants, bakeries) want to buy
equipment without tying up cash. Banks move slowly and require collateral.
LeaseFlow decides in under 2 minutes using an LLM pipeline that analyzes the
merchant's bank statements, POS data, credit history, customer sentiment, and
industry context. Approved merchants pay weekly / biweekly / monthly via
**Stream** (stream.sa, a KSA payment API).

## Two user roles

- **Merchant**: applies for financing, uploads docs, watches analysis run live,
  gets decision, makes repayments. Mobile-first. Plain English. One primary
  action per screen. Target persona: a café owner who's never used a SaaS
  lending app.
- **Admin**: operates the platform. Sees live loan feed, full audit trail of
  every LLM call, can manually override decisions, manages risk policy.
  Desktop-first. Dense, operator-friendly.

## Money mechanics

| Field | Example | Source |
|---|---|---|
| `amount_requested` | 50,000 SAR | merchant input |
| `profit_rate` | 0.15 (15%) | platform config |
| `repayment_months` | 12 | platform config |
| `repayment_frequency` | monthly | merchant picks (daily / weekly / biweekly / monthly) |
| `total_due` | 57,500 SAR | `amount_requested × (1 + profit_rate)` |
| `monthly_payment` | 4,791.67 SAR | `total_due / repayment_months` |
| `approved_amount` | 45,000 SAR or null | set by expert synthesis; can be LESS than requested (partial approval) |
| `amount_paid` | 0 → 57,500 | accumulates as Stream confirms webhook payments |

**Frontend rule**: never recompute this math. Read it off `loans` or
`loans.decision_payload.final_decision`. The backend owns the numbers.

## The pipeline (what the merchant waits for)

```
Merchant submits → POST /analyze/start
      ↓
PHASE A — Per-document extraction (20-60s)
  Each uploaded doc (bank / financial / POS / invoice) is downloaded via
  signed URL, pre-processed with fitz (PDF) or pandas (CSV), sent to MiniMax
  with a strict JSON schema. Output stored in documents.analysis_report.
      ↓
PHASE B — 5 dimensions in parallel (15-30s)
  pos, financial_docs, simah, sentiment, industry — each produces a score
  0-100, confidence, narrative. Each LLM call logged to ai_traces.
      ↓
PHASE C — Expert synthesis (5-10s)
  Deterministic weighted score + hard-floor checks (DSCR ≥ 1.0, SIMAH defaults = 0)
  + MiniMax guardrail review. Writes decision_payload, updates loan.status.
      ↓
On approval: generate installments + Stream payment links + send email
      ↓
Merchant sees decision via Realtime push
```

**Total wall time**: 60-120 seconds. The merchant UI MUST show a warm,
reassuring wait state ("It's okay to close this page — we'll email you").

## Decision outcomes

| Outcome | What merchant sees | What admin sees |
|---|---|---|
| **Approved** | "Approved for X SAR. Your monthly payment is Y." + repayment schedule | Full audit + reason chip + override details |
| **Manual review** | "We're double-checking — we'll be in touch soon" (intentionally vague — admin hasn't decided yet) | Full detail + "Approve at X SAR" / "Deny" actions |
| **Denied** | "We can't finance this at this time." + sanitized reason | Full audit |

## Role-split in one line

- Merchants see `loans.decision_payload.final_decision` + `llm_response.reasoning`.
- Admins see **everything** — documents, dim-level features, trace timeline,
  deterministic rules fired, LLM reasoning, override chains.
- **Never** show admin data on merchant screens.

## Stream payment provider

Stream (stream.sa) is a KSA payment API. We use it to collect installments:

- On loan approval, backend generates one payment link per installment.
- Frontend shows these links as "Pay now" buttons on the payments page.
- Merchant clicks → Stream-hosted checkout → payment → webhook to backend →
  installment marked paid → `loans.amount_paid` bumped → receipt email.
- Frontend sees the status flip via Realtime on `installments`.

The backend Stream client is in `leaseflow/app/payments/stream.py`. Real API
creds are in `.env.leaseflow`. Base URL: `https://api.stream.sa`.

## Tech stack (already chosen, don't argue)

| Layer | Choice |
|---|---|
| Supabase (auth, DB, storage, realtime) | live, schema applied, RLS enforced |
| Orchestrator (FastAPI) | live at `http://localhost:8000` when running locally |
| LLM | MiniMax M2.7 via OpenAI-compatible API |
| Stream | real API + stub fallback when creds missing |
| Frontend | Vite + React 18 + TS + Tailwind + Supabase JS SDK |

## What's out of scope for this build

- **Investor fund pool** — pitch concept only, no backend, do not build.
- **Sales-stream repayment** (daily % of POS sales) — backend supports fixed
  schedules only. Do not build daily-stream UI.
- **Vendor payout tracking** — backend does not track whether we actually
  paid the equipment vendor. Do not build.
- **Arabic localization** — planned, but v1 is English-only. Use neutral
  layouts that could accept RTL later.
- **Mobile native apps** — responsive web only.
- **Analytics / BI** — admin dashboard shows live state, not historical analytics.

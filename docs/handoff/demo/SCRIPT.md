# Demo script — 3 minutes

Click-by-click walkthrough for pitching LeaseFlow. Designed for a 3-min slot
with ~30s buffer. Works on a phone in a pinch.

## Setup (before the pitch)

1. Two browser tabs, side by side if screen allows:
   - **Tab A**: `https://imdadstream.replit.app` (incognito — clean slate)
   - **Tab B**: same URL in another incognito (for admin view later)
2. Keep passwords handy: all 3 demo merchants use `demo123!`

## Act 1 — "The problem" (15 s)

> "Coffee shops in Riyadh need equipment financing. Banks take weeks and
> want collateral. We decide in under 2 minutes using AI."

## Act 2 — The approved merchant (45 s)

1. **Tab A**: Sign in as `qahwa@leaseflow.demo` / `demo123!`
2. "This is Ahmed. He runs a specialty coffee shop. He's asking for a
   50,000 SAR espresso machine."
3. Merchant dashboard shows **1 loan, status: Approved**
4. Click the loan
5. Point at the **decision card**: "Approved for 50,000 SAR. Monthly
   payment 4,791.67 over 12 months."
6. Scroll to the **repayment schedule**: 12 installments, first due next
   month
7. "The AI scored him across 5 dimensions and approved in ~90 seconds end-to-end"

## Act 3 — The denied merchant (30 s)

1. **Tab A**: Log out → sign in as `awful@leaseflow.demo` / `demo123!`
2. Merchant dashboard shows **1 loan, status: Denied**
3. Click the loan → decision card says "We can't finance this at this time"
4. "Same AI, different outcome. This merchant has a credit bureau default
   and their cashflow is 20% of what the loan requires."
5. "No human in the loop — deterministic hard floor blocks it automatically"

## Act 4 — Admin audit trail (60 s, the wow moment)

1. **Tab B**: Log in as admin (your admin account with `role='admin'`)
2. Admin dashboard → live feed of all loans
3. Click into the **Qahwa Haneen** loan (from Act 2)
4. Tab through:
   - **Overview**: final decision, score 74/100, DSCR 2.3x
   - **Documents**: 4 docs — each has confidence, source pages, extracted fields
   - **Decision**: deterministic proposal → rules fired → LLM reasoning → final
   - **Timeline**: 22+ events, every LLM call logged with prompt + response
5. "Every decision is fully auditable. Regulators, merchant disputes, everything."

## Act 5 — Manual review (30 s)

1. **Tab A**: Log out → sign in as `iffy@leaseflow.demo` / `demo123!`
2. "Mixed signals — the AI flagged this for human review"
3. **Tab B** (admin): navigate to this loan
4. Show "Approve with counter-offer 45,000 SAR" / "Deny" buttons
5. "Not every case is clear-cut. When the AI is uncertain, a human decides,
   and that decision is also logged"

## Close (15 s)

- KSA F&B market, Vision 2030 expansion, Stream-powered payments
- "Live demo ran against real Supabase, real MiniMax LLM, real Stream API"

## Fallback if things break live

- If Replit is slow: go straight to `handoff/design/` for static HTML mockups
- If backend errors: all 3 demo loans' data lives in Supabase — admin view
  still works offline from the live URL
- If CF tunnel goes down: backend unreachable. Show the architecture diagram
  instead, narrate what WOULD happen.

## Extra credit (if Q&A gets technical)

- **"What about fraud?"** — the classifier auto-detects doc types via fitz
  keyword vote; extractor LLM sets `meta.low_confidence_fields`; invoice
  extractor has `fraud_flags` (VAT mismatch, inflated pricing).
- **"What's in ai_traces?"** — every LLM call's prompt + response (with
  `<think>` blocks from MiniMax), parsed output, duration, errors. For a
  single loan, 22-30 rows. Admin Timeline tab renders it.
- **"How does Stream collect?"** — one subscription per loan at Stream v2;
  backend monitors webhook → updates `installments.status=paid` → UI flips
  via Realtime.
- **"What's the decision logic?"** — see `handoff/01_OVERVIEW.md` §5 and
  `handoff/02_BACKEND_API.md` for the exact scorer + guardrail behavior.

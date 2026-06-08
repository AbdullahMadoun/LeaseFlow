# Demo package

Everything needed to run the LeaseFlow demo in one folder.

| File | What |
|---|---|
| `CREDENTIALS.md` | 3 golden merchants — emails, passwords, outcomes, loan IDs |
| `SCRIPT.md` | Click-by-click pitch walkthrough (~3 min) |
| `RESEED.md` | How to re-run the seed if demo data gets corrupted |

## The 3 merchants (at a glance)

All passwords: `demo123!`

| Persona | Email | Outcome | Why |
|---|---|---|---|
| Qahwa Haneen Specialty Coffee | `qahwa@leaseflow.demo` | **Approved** 50,000 SAR / 4,791.67 monthly | Strong DSCR 2.3x, SIMAH 787, stable sales |
| Awful Coffee Corner | `awful@leaseflow.demo` | **Denied** (hard floor) | DSCR 0.2 + SIMAH defaults=1 → auto-deny |
| Iffy Burger | `iffy@leaseflow.demo` | **Manual review** | Mixed signals; LLM flagged for human review |

## Live URLs

| | URL |
|---|---|
| Frontend (merchant + admin) | `https://imdadstream.replit.app` |
| Backend API | `https://leaseflow.imdad.website` |
| Health check | `https://leaseflow.imdad.website/health` |

## Quick test from the browser

1. Open https://imdadstream.replit.app
2. Log in as `qahwa@leaseflow.demo` / `demo123!`
3. Dashboard → 1 loan, status **Approved**
4. Click the loan → see decision card, 12 monthly installments
5. Log out, log in as `awful@` → 1 loan, status **Denied**
6. Log out, log in as `iffy@` → 1 loan, status **Manual review**

## Demo walkthrough

See `SCRIPT.md` for the click-by-click pitch narrative.

## What lives behind each merchant

Each one is the product of a real end-to-end pipeline run (not hardcoded):

- **4 real generator-produced PDFs/CSV** in Supabase Storage at `{merchant_id}/{loan_id}/{doc_type}/...`:
  - bank_statement.pdf — 6 months of synthetic KSA bank activity
  - financial_statement.pdf — balance sheet + income statement
  - pos_data.csv — 90 days of transaction-level POS data
  - invoice.pdf — equipment invoice from a fake KSA vendor
- **Real MiniMax extraction** for each doc (confidence 0.85-1.0) stored in `documents.analysis_report`
- **5 dimension_results rows** with real scores, narratives, LLM-backed features
- **Full ai_traces** audit — every LLM call, rule fire, reconciliation logged
- **decision_payload** with deterministic proposal + LLM response + final decision + override reason
- **(Approved only)** 12 installments generated, Stream subscription attempted

See the admin view to inspect everything: `/admin/loans/<loan_id>` — Overview / Documents / Decision / Timeline tabs.

## Known issue: Stream subscription on demo emails

Stream v2 rejects consumer creation for `.demo` / `.test` TLDs ("reserved TLD").
The approved Qahwa Haneen merchant has all 12 installments in the DB but
`stream_payment_url=null` on each. To get working pay-now links:

- re-seed with real-domain emails (see `RESEED.md`), OR
- let the admin UI's "Install schedule" button retry after the CF tunnel is proxied

Decisions themselves are unaffected — only the pay-now button renders as empty.

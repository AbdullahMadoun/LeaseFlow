# DEMO_MODE replay

Demo accelerator: when `DEMO_MODE=true`, `/analyze/start` short-circuits
for three hard-coded merchant emails and replays a previously-computed
decision from a source loan. Total wall clock: **~5-8 seconds** end-to-end,
guaranteed consistent, regardless of MiniMax latency.

## Who replays, and to what outcome

Map lives in `leaseflow/app/orchestrator.py::DEMO_TEMPLATES`:

| Merchant login | Source loan | Outcome |
|---|---|---|
| `ghazal.abdulrazzak@gmail.com` | `13535ea2-47a2-46ba-90d7-b78377e73cf5` (Qahwa) | **approved** · SAR 50k · 12 × SAR 4,792 · Stream subscription created |
| `gzrazak@gmail.com` | `db71e453-d67b-4baf-9544-1fc0f74d883b` (Awful) | **denied** · hard_floor (dscr<1.0 + simah_defaults>0) |
| `a-madoun@hotmail.com` | `490e4f40-5446-48c4-b8a5-f4c36d655c03` (Iffy) | **manual_review** |

Any other email → the real pipeline runs. `DEMO_MODE=false` → the real
pipeline runs regardless.

## What's real vs. replayed

**Real (every demo run):**
- Supabase auth, RLS, role gating
- File upload to storage with the `{merchant}/{loan}/{type}/{uuid}.{ext}` convention
- `POST /documents/classify` — `fitz` keyword classifier on actual bytes
- Required-documents policy check (still 422s if invoice or bank/fin is missing)
- `loans` + `documents` row inserts, Realtime subscriptions
- Stream Consumer + Product + Subscription creation (real API, ~3-5s, background)
- Resend decision email (if `RESEND_API_KEY` is configured)
- Admin timeline (`ai_traces` — copied from source so it looks live)

**Replayed from source loan (copied into new loan's rows):**
- `documents.analysis_report` (matched by `doc_type`)
- `dimension_results.{score, confidence, narrative, result}`
- `loans.decision_payload`, `status`, `approved_amount`, `monthly_payment`
- `ai_traces` rows (loan_id rewritten)

**Transformed before write:**
- `decision_payload.llm_response.reasoning` — source `item_description` +
  `amount_requested` are string-substituted with the new loan's values
  (so "La Marzocco GB5" doesn't appear on a loan that was for a coffee grinder)
- `monthly_payment` is rescaled proportionally to the new loan's amount

## Timing (approximate)

```
 t=0.0s  POST /analyze/start returns immediately with {demo_replay: true}
 t=0.4s  loans.status flips to analyzing, registered_dimensions from source
 t=0.7s  document #1 → done (source report stamped)
 t=1.0s  document #2 → done
 t=1.4s  document #3 → done
 t=1.7s  document #4 → done
 t=2.1s  dim pos → processing
 t=2.5s  dim pos → done (score from source)
 t=3.0s  dim financial_docs → processing → done
 t=3.9s  dim simah → processing → done
 t=4.8s  dim sentiment → done/skipped
 t=5.4s  dim industry → processing → done
 t=5.9s  loans.synthesis_status=done, decision_payload stamped, ai_traces copied
 t=6-10s background: Stream subscription created (on approval) + pay-now URL
         filled via /webhooks/stream INVOICE_CREATED handler
 t=8-15s Resend delivers decision email to the merchant's inbox
```

The frontend's LoanDetail page — which already subscribes to Realtime on
`loans`, `dimension_results`, `documents`, and `installments` — animates
naturally as these events arrive.

## Switching it on

Backend (VM or local):
```
DEMO_MODE=true
```
in `.env` / `.env.leaseflow`. Restart the orchestrator so `CONFIG` picks up
the new value (Config is frozen at import time).

Verify via `/health` — the response shape doesn't currently include
`demo_mode`, so tail the log on the first `/analyze/start` call:

```
INFO orchestrator start_analysis ... demo_replay_dispatch
     parsed={'source_loan_id': '13535ea2-...', 'merchant_email': 'ghazal...'}
```

## Things to NOT do on stage

1. **Don't click "View document" on a demo loan.** The stored PDF bytes are
   whatever the presenter uploaded; the attached `analysis_report` is the
   source merchant's. Admin UI may show the mismatch if you open both.
2. **Don't edit the demo account's email mid-demo.** The replay map is
   keyed on email case-insensitively; changing it breaks the lookup.
3. **Don't expect deterministic Stream invoice URLs.** Each approval creates
   a fresh subscription, so Stream returns a new `https://streampay.sa/s/XXXX`
   URL every run.

## Turning it off

`DEMO_MODE=false`. Restart. Real pipeline runs for every loan, including
from the three demo accounts.

## Removing it entirely

1. Delete the `demo_mode` field from `config.py`
2. Delete the `DEMO_TEMPLATES` dict and `_replay_from_source_loan`,
   `_lookup_merchant_email`, `_substitute_demo_payload` from `orchestrator.py`
3. Delete the `source_loan_id` branch in `start_analysis`
4. Delete `DEMO_MODE=...` lines from `.env.example` and `.env.leaseflow`
5. Delete this file.

No DB migration needed — no tables were added.

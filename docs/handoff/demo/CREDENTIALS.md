# Demo Credentials

Three pre-seeded golden merchants with **real pipeline-produced decisions**.
Real generator-produced PDFs uploaded to Supabase Storage, real MiniMax
extraction, real SIMAH-stub + sentiment + industry dim outputs, real
deterministic scorer, real Stream subscription (for the approved one).

Use these to demo LeaseFlow without waiting on the live pipeline.

**All passwords**: `demo123!`

| # | Persona | Email | Outcome | Amount | Monthly |
|---|---|---|---|---|---|
| qahwa | Qahwa Haneen Specialty Coffee | `qahwa@leaseflow.demo` | **approved** ✅ | SAR 50,000 | SAR 4,791.67 |
| awful | Awful Coffee Corner | `awful@leaseflow.demo` | **denied** ✅ (hard floor) | — | — |
| iffy  | Iffy Burger | `iffy@leaseflow.demo` | **manual_review** ✅ | — | — |

## Details

### Qahwa Haneen Specialty Coffee — Approved
- login: `qahwa@leaseflow.demo` / `demo123!`
- CR: `1010000000`
- SIMAH stub produces: credit 787, defaults 0, active facilities 1 → score 85 (approve)
- Loan: 50,000 SAR for "La Marzocco GB5 espresso machine" · 12 monthly installments
- Generator profile: strong — 95k SAR/mo revenue, 12% volatility, 0 bounces, healthy ratios
- Expected: approved → **got: approved** at full amount
- override_applied: `llm_unavailable_deterministic_only` ⚠ (see Known Issues below)

### Awful Coffee Corner — Denied (hard floor)
- login: `awful@leaseflow.demo` / `demo123!`
- CR: `1010000085`
- SIMAH stub produces: credit 470, defaults 1 → triggers hard floor (`simah_defaults_present`)
- Loan: 80,000 SAR for "Industrial coffee roaster 20kg capacity"
- Generator profile: weak — 22k SAR/mo revenue, 45% volatility, 4 bounces, 2 overdrafts
- Expected: denied → **got: denied**
- override_applied: `hard_floor`
- reason: `Hard floor violation: dscr_below_1.0(0.2), simah_defaults>0(1)`

### Iffy Burger — Manual review
- login: `iffy@leaseflow.demo` / `demo123!`
- CR: `1010000010`
- SIMAH stub produces: credit 639, defaults 0, 4 recent inquiries → caution
- Loan: 60,000 SAR for "Commercial griddle + hood ventilation system"
- Generator profile: mixed — 58k SAR/mo revenue, 28% volatility, 1 bounce
- Expected: manual_review → **got: manual_review**
- override_applied: `llm_unavailable_deterministic_only` ⚠

## Demo tips

- These merchants are RE-runnable: running `seed_demo.py` again will delete
  + recreate the same personas. Credentials + CRs stay constant.
- The decision_payload on each loan has the full deterministic proposal,
  hard floors check, and dimension scores — the admin timeline tab
  (`GET /analyze/trace/{loan_id}`) shows every extraction + dim + rule fire.
- All 4 uploaded documents per merchant are real PDFs/CSVs the admin can
  open. Click through on the admin loan detail `Documents` tab.
- Stream subscription (for approved Qahwa) is created with real Stream
  API — each installment has a pay-now URL. You can test the webhook
  locally with a curl (see `handoff/05_LOCAL_DEV.md`).

## Running the seed

```sh
# From the VM (orchestrator at localhost:8000)
ssh -p 35218 root@159.48.242.1
cd /opt/leaseflow
docker exec -i leaseflow-orchestrator mkdir -p /srv/scripts
docker cp leaseflow/scripts/seed_demo.py leaseflow-orchestrator:/srv/scripts/
docker compose exec -T \
  -e BASE_URL=http://127.0.0.1:8000 \
  -e SEED_PASSWORD=demo123! \
  orchestrator python /srv/scripts/seed_demo.py
```

Takes ~5 minutes (one full pipeline run per merchant × 3).

## Known issues

**LLM synthesis falls back to deterministic on `approved` + `manual_review`.**
Cause: the MiniMax expert LLM returns `dimension_scores.sentiment: null`
when the sentiment dim had a low-confidence placeholder (Google place
not resolved — we use fake Maps URLs for demo). The `LLMDecision`
Pydantic model has `dimension_scores: dict[str, float]` which rejects
null. Deterministic fallback kicks in and the final decision is still
correct, but merchants don't see the rich LLM reasoning text.

Fix (backend, small): loosen `LLMDecision.dimension_scores` to allow
`dict[str, float | None]` OR coerce null→0 during parse. The merchant-
facing UI shows only `decision_payload.llm_response.reasoning` — making
it null degrades to the template fallback copy.

Not blocking the demo; the decisions themselves are right.

## Bonus: making the Awful Coffee hard-floor story crisper

The "hard floor" denial shows off our risk guardrails. In admin
detail → Decision tab, highlight:
```
hard_floors_check.passed = false
hard_floors_check.violations = ["dscr_below_1.0(0.2)", "simah_defaults>0(1)"]
final_decision.override_applied = "hard_floor"
```
That's the "our AI can be overruled by rules" moment.

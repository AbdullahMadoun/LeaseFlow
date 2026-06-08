# 06 — Decisions, Limits, Gotchas

Everything you need to know that isn't in the spec. Read this before you get
surprised.

## Decisions that are locked (don't re-litigate)

1. **All-light neo-brutalist theme.** No dark mode, no theme toggle. Admin
   and merchant screens both use bone `#F9F9F7`. Stitch's deliverables follow
   this — do not deviate.
2. **Tech stack**: Vite + React 18 + TS + Tailwind + React Router + Supabase JS
   + TanStack Query + Zustand. Do not swap to Next.js.
3. **Role enforcement by route prefix**: `/merchant/*` vs `/admin/*`. Not by
   feature flag, not by modal. Wrong route = redirect.
4. **English-only v1**. Arabic is post-demo. Don't build i18n infrastructure
   now; just keep layouts RTL-compatible.
5. **Merchant never sees admin jargon.** DSCR, dimension_scores,
   override_applied, rules_fired, hard_floors — none of these words appear
   on merchant screens. The spec has a rewrite table.
6. **Backend owns all math**. Frontend reads amounts from the DB or API, never
   recomputes.

---

## Stream payment integration — IN FLIGHT 🚧

**Backend is migrating FROM per-installment payment links TO Stream
subscriptions (recurring billing).** The other agent owns this. By the time
you boot, expect:

- `STREAM_BASE_URL` = `https://stream-app-service.streampay.sa` (not `api.stream.sa`)
- One Stream **subscription per loan** (not one link per installment)
- Stream handles billing cadence (our `installments` rows receive webhooks
  as each cycle bills)
- `POST /v2/products` creates the recurring product; `POST /v2/subscriptions`
  starts the billing; webhooks fire per cycle

**What the frontend should assume**:
- The `installments` table stays the authoritative local source of truth for
  "what payments are due / paid". Read from it via Supabase + Realtime.
- Each `installments` row will have **some kind of URL** the merchant can
  click to pay — it might be per-installment (old model) or a single
  subscription checkout URL shared across installments (new model). Just
  render `installment.stream_payment_url` — the backend fills it.
- If `stream_payment_url` is null on an installment, hide the "Pay now"
  button for that row and show a muted "Link unavailable — contact support"
  message. Rare but possible.
- Status transitions (`pending` → `paid`) flow the same way: webhook → backend
  updates row → Realtime push → UI flips.

**What the frontend must NOT do**:
- Call Stream APIs directly. Everything flows through the backend.
- Try to parse Stream webhook payloads. That's backend-only.
- Store any Stream API keys in the browser.

## Limitations you should design around

| Limit | Why | Impact |
|---|---|---|
| Pipeline takes 60-120s end-to-end | MiniMax latency, 4 extractor calls, 5 dim calls, 1 synthesis | Wait UX critical — make it feel calm, not broken. "Close the page, we'll email you." |
| MiniMax occasionally 529s (overloaded) | Their API has capacity limits | Backend falls back to template output on failures. Frontend shouldn't surface MiniMax errors to merchant — it's just "analysis continued with partial data", treat it as normal. |
| Admin override doesn't auto-install repayment schedule | Known backend gap. When admin flips a manual_review → approved via `UPDATE loans`, the backend's `expert.synthesize` isn't re-triggered. | Admin UI should have an "Approve + install schedule" button that both UPDATEs the loan AND calls a backend endpoint (TBD — may need to request) to generate installments. Until that endpoint exists, admin approvals won't get repayment schedules automatically. Flag this in your admin detail tab. |
| Per-document analysis can fail on edge-case PDFs | Real-world PDFs vary wildly; our fitz parser + MiniMax have limits | Show `analysis_report.error` on the document card when `analysis_status === 'error'`. Don't block submission — the pipeline handles a partial doc set. |
| Admin manual-override email not wired | DB webhook on loans UPDATE not created | Merchants won't get an email when an admin manually approves/denies a manual_review. Automated decisions DO send email. Frontend should not rely on emails arriving on override. |
| No account recovery / password reset UI | Using Supabase Auth defaults | If a user forgets their password in a demo, reset via Supabase dashboard. Not a real-user product yet. |
| No document re-upload / replace | RLS blocks merchant UPDATE/DELETE on storage.objects | If a merchant uploads the wrong doc, they need to restart the loan application. Design around this — make the classifier prompt very explicit before the documents row is inserted. |
| No merchant account deletion | Not in scope | — |

## Open questions for the product owner

These are blockers-ish for Stitch-style decisions. Default behaviors in
parens — frontend can implement those; confirm later.

1. **Partial approval framing** — if merchant asked for 50K and we approved
   45K, do we auto-accept and send the 45K schedule, or prompt "Accept 45K
   or re-apply"? (Default: auto-accept.)
2. **Repayment frequency picker** — which step of the wizard? Step 1 (next to
   amount) or step 3 (review)? (Default: step 1.)
3. **Admin counter-offer amount** — is there a floor/ceiling? Can admin
   approve a manual_review at ANY amount, or is it bounded by
   `decision_payload.deterministic_proposal.amount_bounds`? (Default: bounded,
   show those bounds prominently and error on out-of-range.)
4. **Merchant cancellation** — can a merchant cancel a pending loan? An
   approved one? (Default: both allowed; pending cancels silently, approved
   cancels only if no installments paid.)
5. **Admin dashboard defaults** — which status filter is on by default?
   (Default: `manual_review` first — that's where the admin's attention is.)
6. **Document preview** — can admin click a document on the admin detail
   page and see the original PDF inline? (Default: yes, open signed URL in
   a modal with `<iframe>`.)
7. **Investor portal** — on the demo? (Default: not built. Link from admin
   to a "Coming soon" page if you want a pitch-friendly stub.)
8. **Risk policy editor** — admin UI to edit `risk_policies.rules`? (Default:
   read-only display. Policy edits via Supabase dashboard SQL.)
9. **Password strength requirements** — Supabase has defaults (6+ chars).
   Do we add more? (Default: just Supabase's.)
10. **Landing page content** — marketing copy, value props, CTA copy? Stitch
    made placeholder copy — is it OK? (Default: ship Stitch's copy as-is.)

## Known backend endpoints that are STUBBED (fine to call, output is fake)

- **SIMAH dim** — returns deterministic fake credit score based on CR number
  hash. Real integration is out of scope for demo.
- **Sentiment dim** — generates 20 mock reviews keyed off the Google Maps URL
  (deterministic, so same URL → same reviews), then runs real MiniMax aspect
  sentiment on them. The reviews are fake; the LLM analysis is real.
- **Industry dim** — real MiniMax segment classifier + benchmark lookup from
  `segments` table. Location + competition density is mocked.

Admin UI should **not flag these as "stubbed"** to the user — they're the
current product. They return real-looking data. Just know that the upstream
credit bureau / Google Maps integrations aren't live.

## Common confusing things

- **`dimension_results.dimension` vs merchant-friendly names**:
  - `pos` → "Sales health"
  - `financial_docs` → "Can afford"
  - `simah` → "Business trust" (this is the credit score dim, don't say "SIMAH")
  - `sentiment` → "Customer reviews"
  - `industry` → "Industry outlook"
- **`status` vs `synthesis_status`** on `loans`:
  - `status` = the loan's lifecycle state (`pending_analysis` → `analyzing` → `approved`/`denied`/`manual_review`)
  - `synthesis_status` = the pipeline's internal state (`pending` → `running` → `done`). Merchants shouldn't see this. Admins may find it useful on the Timeline tab.
- **`profit_rate` on the merchant UI** — don't show the word "profit rate".
  Merchants experience it as the total repayment amount. Show: "You pay back
  SAR 57,500 over 12 months" rather than "15% profit rate".
- **`override_applied` values** on admin:
  - `agreement` — deterministic + LLM agreed
  - `llm_downgrade` — LLM was stricter than rules (rules proposed approve, LLM pulled to review/deny)
  - `llm_upgrade_blocked` — LLM tried to approve but rules said no; rules won
  - `llm_primary` — configured to let LLM decide unilaterally
  - `llm_unavailable_deterministic_only` — LLM errored, fell back to rules
  - `hard_floor` — failed DSCR<1.0 or SIMAH defaults>0, auto-denied regardless

## Things NOT to worry about

- Deploying the frontend anywhere — do that after demo is nailed locally.
- CI/CD — the hackathon repo has some, don't touch it.
- Production secrets rotation — dev creds are fine for demo.
- Mobile Safari quirks (focus on Chrome/Arc first; polish Safari at end).
- IE11 or anything pre-2022 browser support.

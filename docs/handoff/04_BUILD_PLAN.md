# 04 — Build Plan

5 phases, days-not-weeks. Merchant happy path FIRST so the pitch demo works
end-to-end as soon as possible; admin + polish follow.

**Order discipline**: never start Phase N+1 until Phase N's merchant-facing
flow is demoable end-to-end. "Demoable" means: I can sign up, complete the
flow, and see the result — not "the screen renders".

---

## Phase 1 — Scaffold (Day 1)

**Goal**: React app running at `http://localhost:5173` with Supabase connected,
Tailwind configured with the design tokens, routing with role guards, and
health check hitting the orchestrator.

Setup:
```bash
cd /Users/abdulrazzak/Madoun_Shit/stream-hacka
mkdir frontend
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install @supabase/supabase-js @tanstack/react-query react-router-dom zustand
npm install -D tailwindcss@next @tailwindcss/vite postcss autoprefixer
npm install react-hook-form zod @hookform/resolvers sonner
npm install recharts           # for admin charts
```

Files to create:
- `frontend/.env.example` — list `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`,
  `VITE_VAST_AI_URL`, `VITE_STORAGE_BUCKET`. Document but don't commit real values.
- `frontend/.env.local` — real values from `/Users/abdulrazzak/Madoun_Shit/.env.leaseflow`
- `frontend/vite.config.ts` — Tailwind v4 plugin
- `frontend/tailwind.config.ts` — full neo-brutalist tokens from `03_DESIGN.md`
- `frontend/src/lib/supabase.ts` — singleton Supabase client with typed schema
- `frontend/src/lib/api.ts` — typed fetch wrappers for the orchestrator REST API
- `frontend/src/lib/database.types.ts` — generated from Supabase
- `frontend/src/components/Layout.tsx` — page shell with header
- `frontend/src/App.tsx` — React Router routes + role guards
- `frontend/src/pages/Landing.tsx` — stub with "Apply" button → /signup
- `frontend/src/styles/brutalist.css` — offset-shadow + hover-lift utilities

Commands:
```bash
# Generate typed Supabase schema (requires Supabase CLI)
npx supabase gen types typescript \
  --project-id gbdnlnoqkdislrhvfxol \
  > src/lib/database.types.ts
```

Role guard pseudocode:
```tsx
// /merchant/* requires profiles.role === 'merchant'
// /admin/*    requires profiles.role === 'admin'
// both require auth.getSession() to have a session
// unauthenticated → /login
// wrong role     → / (landing) or the right-role home
```

**Exit criteria for Phase 1**:
- [x] `npm run dev` serves at :5173
- [x] `/` renders with Stitch landing page ported
- [x] `/login` / `/signup` reach Supabase Auth
- [x] After signup, user auto-redirects to `/merchant/onboarding` (stub page)
- [x] Fetch `GET http://localhost:8000/health` works from the browser (CORS open)
- [x] Tailwind tokens render — a button shows the neo-brutalist offset shadow

---

## Phase 2 — Merchant Happy Path (Days 2-3)

**Goal**: a brand new user can sign up, onboard, apply for a loan (upload
docs), watch the pipeline run live, and see a decision. This is the DEMO.

Screens to port (Stitch's HTML already designed them):
1. `handoff/design/signup/code.html` → `/signup`
2. `handoff/design/login/code.html` → `/login`
3. `handoff/design/onboarding/code.html` → `/merchant/onboarding`
4. `handoff/design/merchant_dashboard/code.html` → `/merchant/dashboard`
5. `handoff/design/apply_step_1/code.html` → `/merchant/new-loan` step 1
6. `handoff/design/apply_step_2/code.html` → step 2 (the big one — drag/drop,
   classifier, completeness widget)
7. `handoff/design/apply_step_3/code.html` → step 3
8. `handoff/design/loan_analyzing_clean/code.html` → `/merchant/loans/:id` while analyzing
9. `handoff/design/loan_decided/code.html` → `/merchant/loans/:id` when done

Behaviors to wire:
- **Auth routing**: after login, read `profiles.role` → redirect
- **Onboarding gate**: if merchant user has no `merchants` row, redirect to onboarding
- **Wizard state**: persist draft to `sessionStorage` between steps
- **Step 2 upload flow**:
  - Drag files → upload to Storage at `{merchant_id}/{loan_id}/_pending/{uuid}.ext`
    OR wait to create loan until step 2 submit; easier: create `loans` row
    on step 2 entry (so we have a loan_id for the path), status='pending_analysis'
  - For each uploaded file: `POST /documents/classify` → auto-select type or
    ask user if unknown
  - INSERT `documents` rows
  - Re-evaluate completeness widget (required: invoice + 1 of bank/financial)
  - Enable "Start analysis" button when required set met
- **Step 3 submit**: `POST /analyze/start` → navigate to `/merchant/loans/:id`
- **Loan detail (analyzing state)**:
  - Subscribe to Realtime on `loans` + `dimension_results` + `documents`
  - Show pipeline progress (extraction 0/4 → 4/4, then dims 0/5 → 5/5)
  - Terminal-window wait UX with "It's okay to close this page — we'll email you"
  - When `synthesis_status === 'done'`, swap to decided state
- **Loan detail (decided state)**:
  - Approved: green-tinted decision card, big SAR amount, repayment schedule
    from `installments`
  - Denied: red-tinted, sanitized reason from `llm_response.reasoning`
  - Manual review: yellow-tinted, "we'll be in touch" copy

**Exit criteria for Phase 2**:
- [x] Fresh signup → first decision in < 3 minutes of clicking
- [x] Wait-state feels calm, not twitchy (no spinning spinners every 500ms)
- [x] Decision card renders the right variant
- [x] All copy is merchant-friendly — no "DSCR", "dimension_scores", etc.

---

## Phase 3 — Merchant Payments (Day 4)

**Goal**: approved merchant sees their installment schedule with Stream
"Pay now" links, can click through, and sees status flip when the backend
receives a webhook.

Screens:
- `handoff/design/payments/code.html` → `/merchant/payments`
- `handoff/design/profile/code.html` → `/merchant/profile`

Behaviors:
- Payments page reads `installments` via Supabase (RLS limits to own loans)
- Each row: installment number, due date, amount, status chip, Pay now button
- Pay now → opens `stream_payment_url` in new tab (`target="_blank" rel="noopener"`)
- Realtime subscription on `installments` → UI flips from "pending" to "paid"
  when Stream webhook lands
- Upcoming-payments card on `/merchant/dashboard` (next installment across
  all active loans)
- Profile: display_name edit, logout button

**Testing the webhook locally** (simulate a payment):
```bash
# Get a link_id from one of your test installments
PSQL=<link_id from DB>
curl -X POST http://localhost:8000/webhooks/stream \
  -H "Content-Type: application/json" \
  -d "{\"event\":\"payment.completed\",\"link_id\":\"$PSQL\",\"amount_sar\":4791.67,\"payment_method\":\"mada\",\"transaction_ref\":\"demo_$(date +%s)\"}"
```
The frontend (if subscribed) should see the row flip within ~1s.

**Exit criteria for Phase 3**:
- [x] Payments page shows all installments with correct SAR amounts + due dates
- [x] Clicking "Pay now" opens Stream URL
- [x] Webhook simulation flips the UI in real time

---

## Phase 4 — Admin (Days 5-6)

**Goal**: admin can see every loan, drill into any one, and override manual
reviews.

Screens:
- `handoff/design/admin_dashboard_light/code.html` → `/admin`
- `handoff/design/admin_loan_detail_light/code.html` → `/admin/loans/:id` (4 tabs)
- `handoff/design/admin_risk_light/code.html` → `/admin/risk`
- `handoff/design/admin_segments_light/code.html` → `/admin/segments`

Behaviors:
- **Dashboard**: list of all loans (admin RLS allows SELECT *). Realtime feed
  of new arrivals. Filter chips by status. Click → detail.
- **Loan detail tabs**:
  1. **Overview**: final decision, amount, DSCR, dimension summary chips.
  2. **Documents**: 4 cards (one per doc) showing `analysis_report` fields
     + source_pages + confidence bars. Link to download original file
     (Storage signed URL).
  3. **Decision**: full `decision_payload` rendered — deterministic proposal,
     rules fired, hard floors, LLM response with reasoning, final decision
     with override reason.
  4. **Timeline**: `GET /analyze/trace/{id}` → chronological list of every
     LLM call + rule + aggregation. Expandable rows showing prompt + response
     + parsed JSON.
- **Manual override** (on Overview tab for status=manual_review):
  - "Approve at X SAR" input → UPDATE loans (admin RLS allows)
  - "Deny" button → UPDATE loans SET status='denied'
  - Approval triggers install_schedule_for_loan on next backend tick (or
    reload backend — current setup doesn't auto-fire, admin override is a
    known backend gap — flag it in 06_GOTCHAS.md)
- **Risk banner** (persistent on admin routes): `GET /risk/current` → color-coded banner

**Exit criteria for Phase 4**:
- [x] Admin sees every loan in the feed, live
- [x] Timeline tab renders 20+ trace rows with expand
- [x] Can approve a manual_review loan at a specific amount

---

## Phase 5 — Polish + Edge Cases (Day 7)

- Loading skeletons on every data fetch (no spinners — match the brutalist vibe,
  use gray placeholder boxes with 3px borders)
- Empty states with copy from `FRONTEND_SPEC.md §10`
- Error boundaries (each route wrapped)
- 422 / 404 / 409 error toasts (use `sonner`)
- Accessibility sweep: keyboard nav, focus rings, aria-live on analyzing
- `prefers-reduced-motion` — disable pulse on status dots
- Favicon + OG tags

**Exit criteria for Phase 5**:
- [x] Lighthouse accessibility score ≥ 95
- [x] Every happy path works without a console error
- [x] Backend errors surface as friendly toasts, not crashes

---

## After Phase 5

- Demo mode (replay from `ai_traces` so pitches don't wait on MiniMax)
- Arabic locale (i18n groundwork)
- Native mobile apps (out of scope for demo)
- Investor portal (pitch concept, not real)

## Commit cadence

Commit at each phase boundary. Clear messages:
```
feat(frontend): phase 1 — scaffold + auth + role routing
feat(frontend): phase 2 — merchant wizard + pipeline progress
feat(frontend): phase 3 — payments + Stream link flow
feat(frontend): phase 4 — admin dashboard + loan detail + timeline
feat(frontend): phase 5 — polish + a11y + empty states
```

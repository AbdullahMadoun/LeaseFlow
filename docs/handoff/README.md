# LeaseFlow Frontend — Handoff

You are picking this up fresh. This folder has **everything** you need to build the
LeaseFlow frontend. Read the files in order, then start Phase 1.

## What this is

**LeaseFlow** — a KSA F&B lease-to-own financing platform. Merchant uploads bank
statement / financial statement / POS data / invoice, an LLM pipeline scores
the application across 5 dimensions, produces an approve/deny/manual_review
decision with a repayment schedule, and Stream (the Saudi payment provider)
collects installments. The backend is live and tested end-to-end. Your job
is the frontend.

## Session-starter prompt (paste this into a fresh Claude Code session)

```
I am building the LeaseFlow frontend. The repo is at /Users/abdulrazzak/Madoun_Shit/stream-hacka.
My working branch is feat/leaseflow-backend.

Before doing anything, read these in order:
  1. handoff/01_OVERVIEW.md          — what LeaseFlow is, business logic
  2. handoff/02_BACKEND_API.md       — every endpoint + Supabase direct + Realtime
  3. handoff/03_DESIGN.md            — design system + Stitch's deliverables
  4. handoff/04_BUILD_PLAN.md        — 5-phase plan
  5. handoff/05_LOCAL_DEV.md         — how to run backend + frontend locally
  6. handoff/06_GOTCHAS.md           — decisions, limits, open questions
  7. handoff/07_SKILLS.md            — which Claude Code skills to invoke when

Then read handoff/design/ — there are 18 static HTML screens delivered by the
designer (Stitch). Your job is to port these to a React app at stream-hacka/frontend/.

Start with Phase 1 (scaffold). Invoke the as-frontend-ui-engineering and
as-incremental-implementation skills per 07_SKILLS.md. Commit after each phase
with a clear message.

Backend credentials are in /Users/abdulrazzak/Madoun_Shit/.env.leaseflow — read it
to get SUPABASE_ANON_KEY, SUPABASE_URL, and the Stream key.

If you get blocked, the original backend session is still active — the user can
relay questions. Do not modify backend code unless explicitly requested.
```

## What's in this folder

| File | What it is |
|---|---|
| `README.md` | You are here. |
| `01_OVERVIEW.md` | LeaseFlow product + business logic. Read first. |
| `02_BACKEND_API.md` | Comprehensive API reference. Every endpoint, every payload shape. |
| `03_DESIGN.md` | Neo-brutalist design system + Stitch's component list. |
| `04_BUILD_PLAN.md` | 5 phases, days not weeks, with concrete checklists. |
| `05_LOCAL_DEV.md` | How to boot backend + frontend, test the pipeline. |
| `06_GOTCHAS.md` | Decisions made, what's real vs stubbed, open questions. |
| `07_SKILLS.md` | Which Claude Code skills to invoke when. |
| `design/` | Stitch's 18 static HTML screens + DESIGN.md + PRD. |

## What's authoritative

- **API contract** (payload shapes, RLS, endpoints): `../leaseflow/docs/API_CONTRACT.md`
- **Frontend spec** (view inventory, components, state machines): `../leaseflow/docs/FRONTEND_SPEC.md`
- **Design visuals** (what screens look like): `handoff/design/`
- **Product direction** (mobile/desktop, light/dark, scope): `01_OVERVIEW.md` + `06_GOTCHAS.md`

## Critical decisions already made

1. **All-light neo-brutalist theme** (bone surface `#F9F9F7`, 3px black borders,
   hard offset shadows). Stitch's deliverables follow this. Admin screens are
   also light — not dark. Do not introduce a theme toggle.
2. **Tech**: Vite + React 18 + TypeScript + Tailwind + React Router +
   @supabase/supabase-js + TanStack Query + Zustand. Deploy target: any static
   host (Vercel / Replit / Netlify). See `04_BUILD_PLAN.md` for exact setup.
3. **Role enforcement is by route prefix**: `/merchant/*` vs `/admin/*`. Route
   guards check `profiles.role`.
4. **Merchant-facing copy is plain English** — never show jargon like "DSCR",
   "dimension scores", "override_applied". Full rewrite table in the spec.

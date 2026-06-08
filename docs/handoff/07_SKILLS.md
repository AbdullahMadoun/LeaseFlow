# 07 — Claude Code Skills to Use

Invoke these skills explicitly at the start of relevant work. They give you
concentrated guidance from specialists.

## Primary skill (use constantly)

### `as-frontend-ui-engineering`
**What it does**: Builds production-quality UIs. Focuses on component
composition, layout, state management, and output quality ("production" not
"AI-generated feel").

**When to invoke**: at the start of every phase that creates UI. This is your
default skill for this project.

```
Skill: as-frontend-ui-engineering
```

## Per-phase skills

### `as-spec-driven-development`
**When**: Starting Phase 1 and Phase 2. We have a spec
(`handoff/04_BUILD_PLAN.md` + `FRONTEND_SPEC.md`); this skill enforces
building to spec rather than improvising.

### `as-incremental-implementation`
**When**: Throughout — whenever you feel the urge to do multi-file work in
one commit. This skill splits big changes into small shippable chunks. Good
discipline for the 5-phase plan.

### `as-test-driven-development`
**When**: Phase 2 — the wizard has critical validation logic (file size,
classifier confidence, completeness rule). Write a test for each rule before
implementing. Also useful for payment webhook simulation.

### `as-browser-testing-with-devtools`
**When**: End of every phase to verify. Run the full merchant happy path in
the actual browser. Check Network tab for failed requests, Console for
errors, Realtime websocket frames.

### `as-debugging-and-error-recovery`
**When**: Things break. Don't fix symptoms — use this skill to find root causes.
Common failure modes: RLS 403s (wrong storage prefix), Realtime not
connecting (missing filter), Supabase client caching stale session.

### `as-api-and-interface-design`
**When**: Phase 1 — designing `src/lib/api.ts` (the typed REST client) and
`src/lib/supabase.ts` (the typed Supabase wrapper). These are the contracts
the rest of the app consumes.

## Support skills (use when relevant)

### `as-context-engineering`
**When**: Right now, starting the session. Read handoff/ top to bottom. Set
up working memory notes for the build plan.

### `as-planning-and-task-breakdown`
**When**: Before each phase. Break Phase 2 (which has ~8 screens + 3 complex
flows) into tracked tasks via `TaskCreate`. Don't try to hold it all in head.

### `as-code-simplification`
**When**: End of each phase, after it works. Review what you wrote; remove
premature abstractions; simplify. Small UI codebases rot fast into
over-engineering.

### `as-git-workflow-and-versioning`
**When**: At phase boundaries. Commit with clear messages. Follow the cadence
in `04_BUILD_PLAN.md`. Don't squash mid-phase.

### `as-code-review-and-quality`
**When**: Before submitting any phase as "done". Review your own diff with
this skill's checklist.

### `as-documentation-and-adrs`
**When**: If you make a non-obvious architectural decision (e.g., which
state-management library for a sub-system, or how to handle optimistic
updates), write a short ADR at `stream-hacka/leaseflow/docs/adr/NNN-title.md`.

### `as-shipping-and-launch`
**When**: Demo day prep. Runs the pre-launch checklist.

### `as-performance-optimization`
**When**: After Phase 4 if perf is an issue. Unlikely for this scope —
merchant app is low-traffic, admin is desktop-only — but useful if renders
stutter during Realtime updates.

### `as-security-and-hardening`
**When**: Before "done" claim. Verify: no service keys in frontend, no direct
Supabase writes that bypass RLS expectations, no XSS risks in markdown rendering,
signed-URL TTLs sensible, redirect flows don't leak query params.

### `as-frontend-ui-engineering` (repeat — it's THAT important)
Yes, re-invoke it anytime you're in doubt about a visual or component choice.

## Skills you probably DON'T need

- `as-deprecation-and-migration` — no old frontend to migrate
- `as-ci-cd-and-automation` — existing CI is fine
- `as-idea-refine` — product direction is locked

## Example: Phase 2 skill rotation

```
Start Phase 2 → invoke as-frontend-ui-engineering + as-planning-and-task-breakdown
  Break phase into 8 tasks (one per screen) with TaskCreate
  For the wizard step 2 (complex):
    Invoke as-test-driven-development (write tests for classifier + completeness rule)
  For upload flow specifically:
    Invoke as-debugging-and-error-recovery (RLS prefix issues are common)
End Phase 2 → invoke as-browser-testing-with-devtools
  Run full merchant happy path in browser. Check network + console.
End Phase 2 → invoke as-code-simplification
  Remove premature abstractions before phase 3.
```

## How to invoke a skill

From inside a Claude Code session:
```
Use the as-frontend-ui-engineering skill as I build the wizard step 2 upload flow.
```

Or, when starting a task:
```
Invoke as-spec-driven-development. The spec is at handoff/04_BUILD_PLAN.md Phase 2.
Treat Stitch's handoff/design/apply_step_2/code.html as the visual source of truth.
```

The skill will load its prompt into your context and stay active.

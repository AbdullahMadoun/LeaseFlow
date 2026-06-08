# Analysis Methodology

This is the contract the agent reads at the start of every job and at the start of every loop iteration. The agent is required to follow these phases in order. The phases are also the resume boundaries — if the container restarts mid-job, the worker re-enters whichever phase was active and replays from the last committed step inside that phase.

## Roles

- **Worker** — `scripts/worker.py`. Owns the phase state machine. Calls into the agent for LLM-driven phases. Commits state after every phase transition and after every tool call.
- **Agent** — `scripts/analyst_agent.py`. Holds the LLM client, the system prompt, and the tool loop. Stateless across phases; reads everything it needs from on-disk memory.
- **Sandbox** — `scripts/code_sandbox.py`. Runs the agent's Python in an ephemeral Docker sibling container.

## Phase 1 — Profile the data

Deterministic, no LLM. Lives in `scripts/data_profiler.py`. For each input file:

- Detect format and load with pandas (try CSV, then `;`-separated, then Excel, then JSONL).
- Record: row count, column count, column names + inferred dtypes, missing-value counts per column, duplicate-row count, time range of any datetime-looking columns, distinct counts of any low-cardinality string columns.
- Detect canonical POS columns by name heuristic: `transaction_id`, `branch`/`store`/`location`, `item`/`product`/`sku`, `qty`/`quantity`, `price`/`amount`/`total`, `discount`, `void`/`voided`, `payment_method`, `staff`/`server`/`cashier`, `created_at`/`timestamp`/`date_time`.
- Flag quality issues: future timestamps, negative quantities outside void rows, prices that are zero on non-comp rows, currency mixing, branches with <100 transactions, days with zero transactions inside the covered period.

Output: `memory/data_profile.json`. The agent reads this verbatim in later phases — it must never re-derive these facts.

## Phase 2 — Read the context

LLM, single short call. Reads `input/context.md` plus `data_profile.json`.

The agent extracts:

- Business identity: brand, branch list, region, currency, period covered.
- Stated goals (what does the owner want to know).
- Stated questions (must be answered explicitly in the report).
- Stated problems (the agent must check whether the data supports or contradicts each claim).
- Implicit constraints (e.g. "we just opened a new branch in March" → comparisons should weight pre/post-opening).

Output: `memory/context_summary.json`.

If the context document is empty or generic, the agent records that and proceeds — but it must flag in the final report's analyst notes that no business-specific direction was provided.

## Phase 3 — Plan

LLM, single call, structured output. Inputs: `data_profile.json`, `context_summary.json`.

The plan is an ordered list of investigation questions. Each question carries:

- `id` (`q1`, `q2`, …)
- `text` (the actual question)
- `why` (one sentence — what makes this question worth asking for THIS business)
- `expected_signals` (what kinds of numbers or patterns would constitute an answer)
- `source` (`context` if it came from the brief, `data` if it came from a profile observation, `domain` if it's a standard F&B question)
- `priority` (`critical` | `high` | `normal`)

Mandatory plan rules the agent must satisfy:

- Every explicit question in the context document MUST appear as a `priority: critical` plan item.
- Every stated problem in the context document MUST appear as a `priority: critical` plan item phrased as "Does the data support the claim that X?"
- The plan must cover, at minimum, all eight report sections (revenue, operational patterns, product/menu, branch comparison if multi-branch, risk signals, plus the explicit context items, plus the most important data-driven questions surfaced by the profile).
- `priority: critical` items are answered first.

Output: `memory/plan.json`. The plan is mutable — the agent updates it via the `update_plan` tool during execution.

## Phase 4 — Execute

LLM tool-use loop. The agent picks the next pending plan item and works it. One iteration looks like:

1. Read `state.json`, `plan.json`, recent `findings.jsonl` entries (last 20), and the question being worked.
2. Decide what to compute. State the question and approach in the `purpose` field of `run_python`.
3. Call `run_python` with code. The sandbox returns stdout, stderr, exit code, and runtime.
4. Read the output. Write a one-paragraph observation. Decide:
   - The output answers the question → call `record_finding`, mark the plan item `done` via `update_plan`.
   - The output is partial → run more code.
   - The output is wrong (error, empty, contradicts a prior finding) → diagnose, fix, re-run. Do NOT move on with a broken result.
   - The output surfaced a new important question → add it to the plan via `update_plan` before continuing.
5. Commit memory. Loop.

Tool budget: a soft cap of 80 `run_python` calls per job (configurable via `POS_MAX_CODE_STEPS`). The agent is told the cap and asked to spend deliberately. Hitting the cap forces transition to validation with whatever has been gathered.

Termination of the execute phase requires both:

- All `priority: critical` plan items are `done`, AND
- The agent calls the `finish_analysis` tool.

If the agent calls `finish_analysis` while critical items remain pending, the worker rejects it and pushes the agent to address them.

## Phase 5 — Validate

LLM, no tools, structured output. Reads all of `findings.jsonl`, `plan.json`, and the data profile.

The agent must:

- Find pairs of findings that contradict each other and either resolve or flag them.
- Find findings that reference numbers not present in the run logs (hallucinated metrics) and flag them.
- Find plan questions that are marked done but whose linked findings don't actually answer the question.
- Find missing coverage — sections of the report that won't be fillable from current findings.

Output: `memory/validation.json` with `contradictions`, `hallucinations`, `gaps`, and `recommend_more_investigation` (a list of new plan questions).

If `recommend_more_investigation` is non-empty, the worker pushes those questions onto the plan and re-enters Phase 4 for one more pass. Maximum two validation→execute round trips per job.

## Phase 6 — Report

LLM, single long call, plain markdown output. Inputs: data profile, context summary, plan, every finding, validation result.

The report is the single deliverable. Structure and tone are governed by `references/report-structure.md`. Hard rules:

- Every numerical claim is traceable to a `record_finding` entry, which is traceable to a `run_python` step. The agent cites the finding `id` in a comment-only "evidence map" appended at the end (not shown to the business owner, but written to disk as `memory/evidence_map.md` for audit).
- No vague language. No "could potentially" or "may indicate" without a specific number attached.
- No metric the business owner can't act on.

Output: `memory/report.md` (canonical) and copied to `output/report.md` (served by the API).

## Restart semantics

`state.json` carries `phase`, `phase_started_at`, `last_committed_step`, and the IDs of any in-flight tool call. On restart:

- If `phase ∈ {profile, context, plan, validate, report}` → re-run that phase from scratch. These phases are short and idempotent.
- If `phase == execute` → resume the loop. The agent reads memory just like it would mid-job; the in-flight tool call (if any) is dropped because the sandbox container that owned it is gone.
- If `phase == done` → no-op; serve the report.
- If `phase == failed` → no-op; serve the failure record.

The worker advances `phase` only after the new phase's first commit lands on disk, so a crash exactly at the boundary still resumes correctly.

## Hard guardrails

- The agent must never emit a number not produced by a successful `run_python` call.
- The agent must never claim a finding that contradicts the data profile.
- The agent must never call `finish_analysis` with critical questions still open.
- The sandbox is offline. Any external knowledge needed during execute must come through `web_search` (a separate tool) — never expect the sandbox to reach the network.

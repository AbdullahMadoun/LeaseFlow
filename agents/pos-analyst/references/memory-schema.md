# Memory Schema

Memory is the agent's only persistent state. It is the contract between a crashed worker and a resumed worker. It is also the audit trail.

## Layout on disk

Per-job directory: `${POS_WORK_DIR}/jobs/<job_id>/`

```
<job_id>/
├── input/
│   ├── context.md                 # the business-context document
│   ├── meta.json                  # client-supplied hints (brand, period, etc.)
│   └── data/                      # one or more uploaded data files
│       ├── transactions.csv
│       └── ...
├── memory/
│   ├── data_profile.json          # phase 1 output — deterministic
│   ├── context_summary.json       # phase 2 output
│   ├── plan.json                  # phase 3 output, mutable through phase 4
│   ├── findings.jsonl             # append-only; one finding per line
│   ├── trace.jsonl                # append-only; every tool call + observation
│   ├── code_steps.jsonl           # append-only index of every run_python step
│   ├── code_steps/                # stdout/stderr per run_python call
│   │   ├── step_0001.py
│   │   ├── step_0001.stdout.txt
│   │   ├── step_0001.stderr.txt
│   │   └── step_0001.meta.json
│   ├── validation.json            # phase 5 output
│   ├── evidence_map.md            # phase 6 audit appendix
│   └── report.md                  # canonical final report
├── output/
│   └── report.md                  # served by the API
├── state.json                     # phase + cursor; updated atomically
└── job.log                        # structured logs for this job
```

## File formats

### state.json

```json
{
  "job_id": "j_2026...",
  "phase": "execute",
  "phase_started_at": "2026-04-15T18:01:22Z",
  "step_counter": 47,
  "iteration_in_phase": 12,
  "validation_round": 0,
  "status": "running",
  "model_id": "MiniMax-M2.7",
  "created_at": "...",
  "updated_at": "...",
  "error": null
}
```

`phase ∈ {created, profile, context, plan, execute, validate, report, done, failed}`

`status ∈ {queued, running, done, failed}`

Writes use the write-temp-then-rename pattern so a partial write is never observable.

### plan.json

```json
{
  "version": 3,
  "questions": [
    {
      "id": "q1",
      "text": "Did the lunch slowdown in March happen at all branches or only Branch B?",
      "why": "Owner explicitly raised this in the brief.",
      "expected_signals": "Daily lunch revenue series per branch; comparison Jan-Feb vs March.",
      "source": "context",
      "priority": "critical",
      "status": "done",
      "finding_ids": ["f_0007", "f_0009"],
      "added_in_iteration": 0,
      "completed_in_iteration": 14
    }
  ]
}
```

`status ∈ {pending, in_progress, done, dropped}`. `dropped` requires a `dropped_reason`.

### findings.jsonl

Append-only. One JSON object per line.

```json
{
  "id": "f_0007",
  "ts": "2026-04-15T18:14:55Z",
  "iteration": 14,
  "question_id": "q1",
  "title": "Branch B lunch revenue dropped 38% in March",
  "body": "From Jan-Feb 2026, Branch B's 12:00-14:00 revenue averaged 412 SAR/day across 51 weekdays. In March 2026, the same window averaged 256 SAR/day across 21 weekdays. Other branches in the same window were flat (+/- 4%). The drop is entirely lunch-window: Branch B's morning and evening dayparts were unchanged.",
  "numbers": {"jan_feb_avg_sar": 412.0, "march_avg_sar": 256.0, "delta_pct": -37.9},
  "evidence_step_ids": [21, 22, 24],
  "confidence": "high",
  "tags": ["branch:B", "daypart:lunch", "anomaly"]
}
```

### trace.jsonl

Append-only. Every agent action and observation.

```json
{"ts": "...", "iteration": 14, "kind": "thought", "content": "Lunch drop is the owner's #1 question; need a per-branch daypart slice."}
{"ts": "...", "iteration": 14, "kind": "tool_call", "tool": "run_python", "step_id": 21, "purpose": "Compute branch x daypart revenue Jan-Feb vs March."}
{"ts": "...", "iteration": 14, "kind": "tool_result", "step_id": 21, "exit_code": 0, "stdout_truncated": false, "stdout_path": "memory/code_steps/step_0021.stdout.txt"}
{"ts": "...", "iteration": 14, "kind": "observation", "content": "Pattern is Branch-B-lunch only. Need to confirm not a holiday artifact."}
```

`kind ∈ {thought, tool_call, tool_result, plan_update, finding, error, phase_transition}`.

### code_steps/

Per `run_python` call:

- `step_NNNN.py` — exact code submitted (UTF-8).
- `step_NNNN.stdout.txt` — captured stdout, truncated to `POS_SANDBOX_OUTPUT_LIMIT_KB` (default 256 KB) at the tail.
- `step_NNNN.stderr.txt` — captured stderr, same truncation.
- `step_NNNN.meta.json` — `{"started_at", "ended_at", "exit_code", "wall_seconds", "killed_for_timeout", "stdout_bytes", "stderr_bytes"}`.

The agent always sees a head + tail slice of stdout/stderr in its prompt (configurable, default 8 KB head + 8 KB tail). The full file stays on disk for audit.

### code_steps.jsonl

Append-only index of executed Python steps for easier debugging without scanning the filesystem.

```json
{
  "step_id": 21,
  "started_at": "2026-04-15T18:10:01Z",
  "ended_at": "2026-04-15T18:10:03Z",
  "exit_code": 0,
  "wall_seconds": 1.83,
  "killed_for_timeout": false,
  "stdout_bytes": 1824,
  "stderr_bytes": 0,
  "purpose": "Compute branch x daypart revenue Jan-Feb vs March.",
  "code_path": "memory/code_steps/step_0021.py",
  "stdout_path": "memory/code_steps/step_0021.stdout.txt",
  "stderr_path": "memory/code_steps/step_0021.stderr.txt"
}
```

The API may expose this index through read-only debug endpoints without changing the agent workflow.

## Atomic-write protocol

For every file outside the append-only JSONLs:

1. Write to `<path>.tmp` with `os.fsync` on the file.
2. `os.rename(<path>.tmp, <path>)` — POSIX-atomic on the same filesystem.
3. `os.fsync` on the parent directory.

For JSONL appends:

1. Open with `O_APPEND | O_WRONLY`.
2. Write the line ending in `\n`.
3. `os.fsync`.

A reader of an append-only JSONL is required to skip the trailing line if it does not end in `\n` — that line is from a crashed write and must be discarded.

## State commit order

The worker commits in this order on every transition:

1. Append the corresponding `trace.jsonl` entry (if any).
2. Append/write the artifact (finding, plan, profile, etc.).
3. Atomic-rewrite `state.json` with the new cursor.

If a crash happens between step 2 and step 3, the resumed worker sees the artifact on disk and a stale state. The state machine is written so that re-running the same step produces the same result (idempotent), so a duplicate write is acceptable. Findings have stable IDs derived from the iteration counter; duplicate appends with the same ID are deduplicated on read.

## What memory the LLM sees per turn

Not all of disk goes into the prompt. The agent receives, at every execute-phase turn:

- The system prompt (cached).
- The data profile (cached).
- The context summary (cached).
- The current plan (NOT cached — it changes).
- The last 20 findings as compact JSON.
- The last 10 trace entries.
- The current question being worked.
- The most recent tool result (stdout/stderr head+tail).

Everything else lives on disk and is queryable via `run_python` if the agent needs to look back.

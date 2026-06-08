---
name: pos-financial-analyst
description: "Autonomous financial analyst agent for point-of-sale transaction data from restaurants and cafés. Accepts CSV data plus a free-text business context via API, runs an end-to-end ReAct analysis loop (profile → plan → execute → validate → report) with Docker-sibling sandboxed code execution, persistent crash-safe memory, and Anthropic Claude Sonnet 4.6 as the reasoning model. Produces a non-technical business report grounded in computed findings. Ships as a docker-compose stack and deploys to Vast.ai via the bundled `vast-docker-remote-compute` resources."
---

# POS Financial Analyst

## What this is

An autonomous agent service that behaves like a senior financial analyst with a data-science background. It takes POS transaction data and a business-context document, runs a full investigation loop without human intervention, and returns a specific, grounded report a non-technical business owner can act on.

## Execution model on Vast

- Deploy as a **VM instance** on Vast.ai (not a standard Docker-only instance), so the remote host itself can run Docker and docker-compose alongside this and any other services you put on the box.
- Inside the VM, `docker-compose` runs the API service (`pos-analyst-api`).
- The API container mounts `/var/run/docker.sock` and spawns **sibling sandbox containers** per code-execution step. This is Docker-socket sharing, not Docker-in-Docker — safer, and supported on any VM host with a Docker daemon.
- Each sandbox run is ephemeral, offline (`network=none`), read-only root filesystem, resource-limited, runs as `nobody`, and gets the job's input mounted read-only plus a private scratch mount.

## Components

```
SKILL.md                            ← this file
agents/pos_analyst.yaml             ← model + entrypoint prompt
references/
  analysis-methodology.md           ← the 6-step loop, phase outputs, restart semantics
  fnb-benchmarks.md                 ← typical F&B KPI ranges the agent can use as priors
  report-structure.md               ← required report sections + tone
  memory-schema.md                  ← on-disk memory layout (resumable)
  vast-workflow.md                  ← Vast API + VM selection (shared with deploy)
scripts/
  config.py                         ← env + paths
  models.py                         ← pydantic job / plan / finding / state
  memory.py                         ← atomic writes, JSONL append, resume helpers
  data_profiler.py                  ← deterministic pandas profile (schema, coverage, quality)
  code_sandbox.py                   ← spawn docker-sibling sandbox containers
  external_knowledge.py             ← web-search tool (Anthropic server tool, gated)
  prompts.py                        ← system prompts, tool schemas, cache control
  analyst_agent.py                  ← the phase state machine + tool-use loop
  report_generator.py               ← final-report synthesis pass
  worker.py                         ← job runner: picks pending jobs, drives the agent
  api_server.py                     ← FastAPI: POST /jobs, GET /jobs/{id}, GET report
  entrypoint.sh                     ← container entrypoint (resume + serve)
  Dockerfile                        ← API image (python + docker CLI)
  Dockerfile.sandbox                ← sandbox image (pandas/numpy/scipy, no net)
  docker-compose.yml                ← full stack
  requirements.txt                  ← API deps
  sandbox_requirements.txt          ← sandbox deps
  deploy_vast.py                    ← one-shot: create VM, push stack, bring it up
  vast_probe.py                     ← Vast API helper (shared; see vast-workflow.md)
```

## Lifecycle

1. Client `POST /jobs` with multipart: one or more CSVs + a `context.md` + optional JSON hints. Returns a `job_id`.
2. Worker picks the job, runs phases:
   - **Profile** data (deterministic; no LLM)
   - **Read context** (LLM, short)
   - **Plan** (LLM, emits a question list with ordering rationale)
   - **Execute** (LLM tool-use loop: `run_python`, `record_finding`, `update_plan`, `web_search`, `finish_analysis`)
   - **Validate** (LLM pass over findings; may re-enter Execute)
   - **Report** (LLM produces the final markdown for a non-technical reader)
3. Every phase commits state atomically before advancing. Mid-loop commits after every tool call. If the container restarts, `entrypoint.sh` calls `worker.py --resume`, which reads `state.json` + `memory/*.jsonl` and re-enters the current phase.
4. Client `GET /jobs/{id}/report` returns the final markdown.

## How to work with this skill

- For **deploying to Vast**, follow `references/vast-workflow.md` and use `scripts/vast_probe.py` + `scripts/deploy_vast.py`. Choose a **VM-capable** offer because the workload here needs a real Docker daemon on the host.
- For **running locally** (dev and tests), `scripts/docker-compose.yml` is the entry point. Nothing in the stack assumes Vast.
- For **adding new analytical capabilities**, the agent is driven by `references/analysis-methodology.md` and the tool schemas in `scripts/prompts.py`. Update those together — the methodology is the contract the agent reads.
- For **debugging a failed job**, open `workdir/jobs/<job_id>/memory/` on the host; every tool call, stdout, and finding is on disk in JSONL.

## Cost and model

- Analyst model: **`MiniMax-M2.7`** via the MiniMax OpenAI-compatible endpoint (`https://api.minimax.io/v1`). M2.7 is purpose-built for agentic harnesses with tool calling, has a 200K context, and runs at ~$0.30 / $1.20 per M input/output tokens.
- Optional `MiniMax-M2.7-highspeed` variant (~3× faster) selectable via `POS_MODEL_ID` env.
- The LLM client is just the OpenAI Python SDK pointed at MiniMax — swapping providers later is a one-line `base_url` + `model` change.

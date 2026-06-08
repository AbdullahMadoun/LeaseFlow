# Context — what's been done

Snapshot of the POS analyst initiative as of **2026-04-16**. If you're new to this branch (or future-you coming back after a break), read this first.

## What this project is

An autonomous financial-analyst service for restaurant/café POS data. Clients POST a CSV + a free-text business context over HTTP; the backend runs a multi-phase ReAct loop against **MiniMax-M2.7** (reasoning + tool calling + code writing), executes the analyst's Python in a sandboxed sibling container, and returns a non-technical business report grounded in computed findings. Lives on this branch of `stream-hacka` alongside (but independent of) the StreamFlow hackathon demo.

## Build history (what was actually done)

### 1. Specified the system (2026-04-15)
- Read the 6-phase autonomous-analyst spec (profile → context → plan → execute → validate → report) and the hard guardrails (every number must be computed; sandboxed code exec; crash-safe memory; non-technical report target).
- Chose stack: **MiniMax-M2.7** over the OpenAI-compat endpoint (purpose-built for agentic tool calling, 200K ctx, $0.30/$1.20 per M tokens). Kept OpenAI Python SDK so the client is a one-line swap to another provider later.
- Chose deploy target: **Vast.ai VM** (not a standard Vast container), because the workload needs a real Docker daemon on the host — the API container spawns per-step sibling sandbox containers via the mounted socket. Standard Vast instances don't support Docker-in-Docker.

### 2. Wrote the codebase
Under `pos-analyst/`:
- `SKILL.md` — skill-style entry doc + component map
- `agents/pos_analyst.yaml` — model config (M2.7 default, M2.7-highspeed optional via env)
- `references/` — the agent's "contract" + priors:
  - `analysis-methodology.md` — the 6-phase state machine the agent reads every turn
  - `fnb-benchmarks.md` — F&B operational priors (QSR/casual-dining ranges, Ramadan/holiday caveats)
  - `report-structure.md` — required report sections + tone rules
  - `memory-schema.md` — on-disk layout, atomic-write + JSONL-append protocol, resume contract
  - `vast-workflow.md` — (pre-existing) Vast API surface + VM-capable rental rules
- `scripts/` — the service itself:
  - `config.py`, `models.py`, `memory.py` — env config, pydantic schemas, atomic persistence
  - `data_profiler.py` — deterministic Phase 1 (schema detection, role mapping, quality flags)
  - `code_sandbox.py` — sibling-Docker spawn (`--network=none --read-only --user 65534 --cap-drop ALL --no-new-privileges`, cpu/mem/pids limits, head+tail output capture)
  - `external_knowledge.py` — Tavily web-search adapter (off by default, per-job budget)
  - `prompts.py` — `SYSTEM_PROMPT`, 5-tool schema (`run_python`, `record_finding`, `update_plan`, `web_search`, `finish_analysis`), per-phase instruction blocks
  - `analyst_agent.py` — phase orchestration + tool-use loop, MiniMax multi-turn `tool_calls` echo contract, dynamic-context refresh, finish-guard, retry/backoff
  - `report_generator.py` — final synthesis + audit-appendix split
  - `worker.py` — phase advancer, idempotent boundaries, validate→execute round-trips, resume-all sweep
  - `api_server.py` — FastAPI (`/health`, `POST /jobs`, `GET /jobs/{id}`, `/report`, `/trace`, `/findings`), thread-pool worker, lifespan resume
  - `entrypoint.sh` — sandbox image ensure + uvicorn
  - `Dockerfile` + `Dockerfile.sandbox` + `docker-compose.yml` — two-image stack, socket mount, healthcheck
  - `deploy_vast.py` — one-shot VM provisioning with bandwidth-first offer scout
  - `vast_probe.py` — (pre-existing) Vast API helper

### 3. Verified it (before burning $ on a VM)
- AST-parsed every `.py` — all 13 files clean
- Import-smoke: `config.CONFIG.model_id == "MiniMax-M2.7"`, 5 tool schemas present, pydantic models round-trip
- Profiler smoke on synthetic POS CSV → correctly detected `branch`/`item`/`qty`/`timestamp` roles + surfaced "negative qty but no void column → implicit voids" quality flag

### 4. Set up CI/CD
- `.github/workflows/ci.yml` — on push/PR to `pos-analyst/**`: AST parse + import smoke + profiler smoke + docker buildx (both images, GHA cache)
- `.github/workflows/deploy.yml` — manual dispatch or `pos-analyst-v*` tag push → SSH to VM → `git pull` → `docker compose up -d --build` → `/health` gate
- Docs:
  - `docs/MINIMAX_SETUP.md` — get/rotate key, variant selection, tuning knobs
  - `docs/DEPLOYMENT.md` — zero-to-live runbook
  - `docs/CICD.md` — pipeline contract + required secrets/vars
  - `docs/INFRASTRUCTURE.md` — target architecture + subdomain plan + auth phases

### 5. Scouted Vast.ai for cheap + bandwidth-fat VMs
- Discovered there's no true CPU-only VM market on Vast — every VM-capable host has a GPU attached (which we leave idle)
- Found the sweet spot: **symmetric ≥1 Gbps**, verified, ~$0.10/hr tier
- Hardened `deploy_vast.py` with bandwidth filters by default and added a `scout` subcommand so future rentals always pick a fat-pipe host (offer IDs churn; don't hardcode one)

### 6. Domain + DNS
- Bought **`imdad.website`** on GoDaddy (AED 3.64 first year). **Auto-renew must be turned off** to dodge the AED 147 renewal.
- Added to Cloudflare free plan, zone `imdad.website`
- Nameservers at GoDaddy flipped to Cloudflare's (`selah.ns.cloudflare.com`, `walt.ns.cloudflare.com`)
- Cloudflare confirmed zone active ("Your domain is now protected by Cloudflare")
- SSL mode set to **Full (strict)**
- Five default GoDaddy DNS records imported (2× parking A records, `_domainconnect` CNAME, `www` CNAME, DMARC TXT) — the two parking A records will get deleted once we know what the apex should point to (Replit)

## Current state

| Layer | State |
|---|---|
| Code | ✅ Pushed, CI ready, not yet deployed anywhere |
| Domain | ✅ `imdad.website` active on Cloudflare (free plan) |
| SSL | ✅ Full (strict) mode on |
| Frontend hosting | ⏳ Replit (keep as-is); custom domain not yet wired |
| Backend hosting | ❌ Vast VM not yet rented |
| Cloudflare Tunnel | ❌ Not yet created (needs VM first) |
| Auth | MVP: `POS_API_KEY`. Phase-2 plan: CF Access Service Tokens |

## Key decisions and why

| Decision | Reasoning |
|---|---|
| MiniMax-M2.7 as analyst model | Purpose-built for agentic harnesses; cheap; 200K context fits multi-file POS data |
| Vast VM (not standard Vast container) | Workload runs Docker on the host; DinD not supported on standard instances |
| Docker-sibling sandbox (not in-process exec) | Real isolation: offline, read-only, capability-dropped, unprivileged user, resource-limited |
| Sonnet-style atomic JSONL + state.json | Cheap crash-safe persistence without adding a DB dependency |
| One repo for StreamFlow + POS analyst (branch isolation) | Hackathon speed; extracting later is a `git filter-repo` away |
| Keep Replit for frontend | Already works; mid-hackathon migrations are how demos die |
| GoDaddy for domain (not CF Registrar) | User was already mid-cart; $1 is fine for one year if auto-renew is off |
| `imdad.website` TLD | Cheap first year, judges don't care about TLD |
| Bandwidth-first VM filter by default | This VM is backend-for-many-services; fat pipe matters more than marginal $/hr |
| `POS_API_KEY` for MVP, CF Access Tokens for prod | Minimum auth to demo; real auth is a 1-PR swap before any customer |

## Files that matter most

| File | Read when |
|---|---|
| `pos-analyst/SKILL.md` | You want the skill overview |
| `pos-analyst/docs/DEPLOYMENT.md` | You're provisioning or redeploying |
| `pos-analyst/docs/INFRASTRUCTURE.md` | You need the DNS + auth plan |
| `pos-analyst/docs/CICD.md` | You need to set up secrets/vars or troubleshoot the workflow |
| `pos-analyst/docs/MINIMAX_SETUP.md` | You're getting or rotating the API key |
| `pos-analyst/references/analysis-methodology.md` | You're modifying how the agent reasons |
| `pos-analyst/references/memory-schema.md` | You're debugging a stuck/failed job |
| `pos-analyst/scripts/deploy_vast.py` | You're renting or tearing down a VM |

## What's next (short list)

1. Wire `imdad.website` apex → Replit (custom domain in Replit, CNAME/A in CF DNS, delete the two GoDaddy parking A records)
2. Rent Vast VM: `deploy_vast.py scout` then `up`
3. Create Cloudflare Tunnel + hostname `api.imdad.website`
4. Land **PR #2**: `cloudflared` container in compose + CORS middleware allowlisting the Replit origin + `CLOUDFLARE_TUNNEL_TOKEN` secret
5. E2E test from a fresh browser: `imdad.website` → frontend → `api.imdad.website/jobs` → report comes back
6. Set a `cron-job.org` 4-min ping on the Replit URL to keep the frontend warm for the pitch

## Commit history on this branch

```
d16a81e  docs(pos-analyst): add INFRASTRUCTURE.md — domain + Replit + Vast plan
4588ee3  feat(pos-analyst): autonomous F&B POS analyst backend + CI/CD
6db0079  Build multi-page StreamFlow hackathon demo website   (← main; predates this branch)
```

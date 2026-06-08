# LeaseFlow Deployment

## Prerequisites

- Vast.ai VM (not a standard container instance — the analyst requires a real
  Docker daemon for sibling containers). Use `pos-analyst/scripts/deploy_vast.py`
  or provision manually.
- Supabase project: `gbdnlnoqkdislrhvfxol` (credentials in `.env`).
- MiniMax API key.

## One-command deploy (from repo root on the VM)

```sh
set -a && . .env && set +a    # load secrets
docker build -f pos-analyst/scripts/Dockerfile.sandbox \
             -t pos-analyst-sandbox:latest pos-analyst/scripts/
docker compose up -d --build
```

Verify:

```sh
curl http://<vast-host>:8080/health   # analyst
curl http://<vast-host>:8000/health   # orchestrator
```

Expected orchestrator health:

```json
{
  "status": "ok",
  "ts": "2026-04-16T...",
  "env": "production",
  "supabase": {"reachable": true, "error": null},
  "analyst": {"configured": true, "reachable": true, "model": "MiniMax-M2.7"},
  "llm_model": "MiniMax-M2.7",
  "decision_mode": "guardrail"
}
```

## Services

| Service        | Port | Role                                        |
|----------------|------|---------------------------------------------|
| `analyst`      | 8080 | POS/financial agent engine (existing code)  |
| `orchestrator` | 8000 | LeaseFlow API (what the frontend calls)     |

They run on the same Docker bridge network. The orchestrator reaches the
analyst via `http://analyst:8080`. The orchestrator auto-submits a supplemental
single-business analyst job after Phase A extraction and exposes it via:

- `GET /analyze/status/{loan_id}` under `analyst_jobs`
- `POST /analyze/analyst/start/{loan_id}`
- `GET /analyze/analyst/status/{loan_id}`
- `GET /analyze/analyst/report/{loan_id}`

## Schema migrations

Already applied to `gbdnlnoqkdislrhvfxol`. To re-apply on a fresh project:

```sh
# From the host (needs SUPABASE_ACCESS_TOKEN with project access)
python3 leaseflow/scripts/apply_migrations.py
```

SQL files are `leaseflow/migrations/0001..0004_*.sql`. Apply in order.

## Configuring the frontend

Point `VAST_AI_URL` to `http://<vast-host>:8000`. See
`leaseflow/docs/API_CONTRACT.md` for full payload shapes and example flows.

## Common operations

```sh
docker compose logs -f orchestrator      # tail orchestrator logs
docker compose logs -f analyst           # tail analyst logs
docker compose restart orchestrator      # restart just the orchestrator
docker compose down && docker compose up -d --build    # full rebuild
```

## Known deployment quirks

- The analyst needs the SAME absolute path on host and inside the container
  for `POS_HOST_WORK_DIR` because the docker socket relays sibling-mount
  paths from the container's perspective. Default: `/var/pos-analyst`.
- If you see the orchestrator start before the analyst, `depends_on: service_healthy`
  delays it until `/health` is 200. First boot takes ~20s.
- `DECISION_MODE=guardrail` (default) means the LLM can only downgrade
  (approve → manual_review → deny). Set `DECISION_MODE=llm_primary` to let
  the LLM's decision stand (still subject to hard floors).
- `LEASEFLOW_DEV_FIXTURES=true` mounts `POST /dev/generate-fixtures` which
  creates fake documents (bank statement, financial statement, POS CSV,
  invoice) for any loan and uploads them to Storage. Leave this off in
  production — it lets anyone populate test docs on a loan they don't own.

## Audit trail

Every LLM call, rule fire, aggregation, reconciliation, and extraction event
writes a row to the `ai_traces` table. `GET /analyze/trace/{loan_id}` returns
the full chronological timeline for a loan (admin-only by RLS on the table).
Useful for debugging a decision, replaying a loan against a changed model,
or showing the admin UI timeline view.

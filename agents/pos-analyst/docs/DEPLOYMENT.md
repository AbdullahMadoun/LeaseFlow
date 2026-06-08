# Deployment runbook

From empty → live backend. ~15 minutes end-to-end.

## Prerequisites

- A MiniMax API key with billing enabled → [MINIMAX_SETUP.md](MINIMAX_SETUP.md)
- A Vast.ai account with API key (saved at `~/.config/vastai/vast_api_key` or exported as `VAST_API_KEY`)
- SSH keypair on your laptop (`~/.ssh/id_ed25519`). Generate if missing: `ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519`
- `python3` (for `deploy_vast.py`), `rsync`, `ssh`, `docker` locally (local builds are optional)

## Step 1 — Pick an offer

Offers churn. Scout the current pool before renting:

```bash
cd pos-analyst/scripts
python3 deploy_vast.py scout --limit 10
```

The ranker enforces a **1 Gbps floor on both directions**, verified hosts, ≥16 cores, ≥32 GB RAM. Pick an id. If you want more bandwidth headroom, raise the floor:

```bash
python3 deploy_vast.py scout --min-net-up-mbps 2500 --min-net-down-mbps 2500
```

## Step 2 — Rent + first deploy

The `up` command provisions the VM, installs Docker on it, rsyncs this directory, writes `.env`, builds the sandbox image, and brings up compose.

```bash
export VAST_API_KEY="$(cat ~/.config/vastai/vast_api_key)"
export MINIMAX_API_KEY="sk-your-minimax-key"
export POS_API_KEY="$(openssl rand -hex 24)"   # save this — clients need it

python3 deploy_vast.py up \
  --pos-api-key "$POS_API_KEY" \
  --min-net-up-mbps 1000 --min-net-down-mbps 1000 \
  --disk-gb 80
# Or pin a specific offer from `scout`:
# python3 deploy_vast.py up --offer-id 26750939 --pos-api-key "$POS_API_KEY" --disk-gb 80
```

The script prints `instance_id`, SSH line, and API URL at the end. Save the instance id — you'll need it to destroy the VM later.

Smoke test the API:

```bash
curl -s http://<VM_HOST>:8080/health | jq .
# { "ok": true, "model": "MiniMax-M2.7", ... }
```

## Step 3 — Submit your first job

```bash
curl -s -H "X-API-Key: $POS_API_KEY" \
  -F "context=<paste free-text brief here>" \
  -F "files=@sample_transactions.csv" \
  http://<VM_HOST>:8080/jobs
# → {"job_id":"j_xxxx","status":"queued",...}

# Multi-file daily financial schema example:
# curl -s -H "X-API-Key: $POS_API_KEY" \
#   -F "context_file=@examples/strema_portfolio_context.md" \
#   -F "files=@generated_dataset_v2/merchants.csv" \
#   -F "files=@generated_dataset_v2/sales_daily.csv" \
#   -F "files=@generated_dataset_v2/payments_daily.csv" \
#   -F "files=@generated_dataset_v2/bank_daily.csv" \
#   -F "files=@generated_dataset_v2/obligations.csv" \
#   http://<VM_HOST>:8080/jobs

curl -s -H "X-API-Key: $POS_API_KEY" http://<VM_HOST>:8080/jobs/j_xxxx | jq .
# phase progresses: created → profile → context → plan → execute → validate → report → done

curl -s -H "X-API-Key: $POS_API_KEY" http://<VM_HOST>:8080/jobs/j_xxxx/report
curl -s -H "X-API-Key: $POS_API_KEY" http://<VM_HOST>:8080/jobs/j_xxxx/trace | jq .
curl -s -H "X-API-Key: $POS_API_KEY" http://<VM_HOST>:8080/jobs/j_xxxx/steps | jq .
# Full code/stdout/stderr for a specific Python step:
curl -s -H "X-API-Key: $POS_API_KEY" http://<VM_HOST>:8080/jobs/j_xxxx/steps/1 | jq .
```

## Step 4 — Convert the VM to GitOps (so redeploys don't need your laptop)

On the VM, swap the rsync checkout for a `git clone` so `deploy.yml` can pull on each push:

```bash
ssh root@<VM_HOST>
cd /opt
mv pos-analyst pos-analyst.rsync-backup
git clone --depth 1 --branch feat/pos-analyst \
  git@github.com:Alkerm/stream-hacka.git pos-analyst
cp pos-analyst.rsync-backup/pos-analyst/scripts/.env pos-analyst/pos-analyst/scripts/.env
cd pos-analyst/pos-analyst/scripts && docker compose --env-file .env up -d --build
```

For a **private** repo, create a GitHub **deploy key** (Settings → Deploy keys → Add) using the VM's own key:

```bash
ssh root@<VM_HOST> 'cat ~/.ssh/id_ed25519.pub || (ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -q && cat ~/.ssh/id_ed25519.pub)'
```

Paste the output into GitHub as a **read-only** deploy key. Then `git clone git@github.com:...` works on the VM.

## Step 5 — Wire GitHub Actions deploy

1. Repo → Settings → Secrets and variables → Actions → create:
   - `MINIMAX_API_KEY` (secret)
   - `POS_API_KEY`     (secret — same value you used in step 2)
   - `SSH_PRIVATE_KEY` (secret — contents of your laptop's `~/.ssh/id_ed25519`, the private half)
2. Same page, **Variables** tab:
   - `VM_HOST` = VM public IP
   - `VM_PORT` = `22`
   - `VM_USER` = `root`
   - `VM_REMOTE_DIR` = `/opt/pos-analyst`
   - `VM_GIT_REPO` = your repo's SSH URL
   - `VM_GIT_REF`  = `feat/pos-analyst` (initially), then `main` after you merge
3. Repo → Settings → Environments → new environment `production`. Optionally require a reviewer.
4. Actions → `pos-analyst deploy` → Run workflow → done. Every run from now on does the full redeploy on its own.

## Day-2 operations

| Task | How |
|---|---|
| Redeploy latest code | Actions → `pos-analyst deploy` → Run workflow |
| Force clean rebuild | Same, with `rebuild: true` |
| Pin a ref | Same, with `git_ref: <tag or sha>` |
| Rotate MiniMax key | Update `MINIMAX_API_KEY` secret → re-run deploy |
| Read a failed job | `ssh root@<VM_HOST> 'cat /var/pos-analyst/jobs/<job_id>/memory/trace.jsonl'` |
| Check container logs | `ssh root@<VM_HOST> 'docker logs -f pos-analyst-api'` |
| Resize disk | Not possible on Vast. Provision a new, larger VM; the workdir is a bind mount so you can rsync `/var/pos-analyst` over |
| Destroy VM | `python3 deploy_vast.py down --instance-id <id>` |

## If the deploy workflow fails

The most common causes and fixes:

| Symptom | Cause | Fix |
|---|---|---|
| SSH "permission denied (publickey)" | `SSH_PRIVATE_KEY` secret doesn't match the VM's authorized_keys | Re-paste the private key; confirm the VM has the matching public key in `/root/.ssh/authorized_keys` |
| `git clone` fails on private repo | No deploy key on the VM | Step 4 above |
| `docker: Cannot connect to the Docker daemon` | Docker not installed on the VM | First-time `deploy_vast.py up` does this; if the VM was provisioned differently, run `curl -fsSL https://get.docker.com \| sh && systemctl enable --now docker` |
| `/health` never succeeds | Sandbox image failed to build; API container starts but jobs fail preflight | `ssh root@VM 'docker logs pos-analyst-api'` — look for `Sandbox image 'pos-analyst-sandbox:latest' is not available` |
| Jobs stuck in phase=execute forever | Step budget exhausted with critical questions open — the worker will force-transition on next turn | `GET /jobs/{id}/trace` to inspect; raise `POS_MAX_CODE_STEPS` in env if legitimate |

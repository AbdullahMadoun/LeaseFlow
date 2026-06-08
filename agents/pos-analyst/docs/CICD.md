# CI/CD

Two workflows, one promotion path.

## Pipelines

### `ci.yml` — runs on every push / PR touching `pos-analyst/**`

| Job | What it does | Why |
|---|---|---|
| `lint-and-import-smoke` | AST-parses every `.py`, installs deps, imports `config`/`models`/`prompts`, round-trips pydantic models, runs the data profiler on a synthetic CSV | Catches 90% of "I renamed something" and "the agent's tool schemas don't match" regressions in <60s |
| `docker-build` | Builds both the `api` and `sandbox` images via buildx with GHA cache | Catches Dockerfile rot and missing system deps before deploy |

Passing CI is the signal that a branch is safe to deploy. It does **not** run the agent end-to-end (that needs a MiniMax key — we don't spend credits on every PR).

### `deploy.yml` — manual dispatch or tag push

Triggers:
- `workflow_dispatch` with optional `git_ref` and `rebuild` inputs
- Git tag push matching `pos-analyst-v*` (use this to mark releases you want auto-deployed)

What it does:
1. Installs the `SSH_PRIVATE_KEY` secret into the runner
2. SSHes to `VM_USER@VM_HOST:VM_PORT`
3. On the VM: `git clone` (first time) or `git fetch && git reset --hard` (subsequent), at the resolved ref
4. Writes `${remote}/pos-analyst/scripts/.env` with `MINIMAX_API_KEY` + `POS_API_KEY` (mode 600)
5. Rebuilds the sandbox image (`docker build -f Dockerfile.sandbox -t pos-analyst-sandbox:latest .`)
6. Brings up compose (`docker compose up -d --build`)
7. Polls `/health` six times with 10s backoff before calling the deploy successful

Concurrency guard: `concurrency: pos-analyst-deploy` prevents two deploys from racing on the same VM.

## Required GitHub configuration

### Secrets (Settings → Secrets and variables → Actions → Secrets)

| Name | Used by | Content |
|---|---|---|
| `MINIMAX_API_KEY` | deploy | MiniMax API key for the analyst |
| `POS_API_KEY` | deploy | Random 32+ char token clients must send as `X-API-Key` |
| `SSH_PRIVATE_KEY` | deploy | Private key whose public half is in the VM's `~/.ssh/authorized_keys` |

### Variables (same page → Variables)

| Name | Example | Notes |
|---|---|---|
| `VM_HOST` | `64.31.25.170` | Public IP from `vast_probe show-instance` |
| `VM_PORT` | `22` | Direct SSH port; Vast VMs expose 22 on their public IP |
| `VM_USER` | `root` | Vast VMs use root |
| `VM_REMOTE_DIR` | `/opt/pos-analyst` | Top-level checkout path on the VM |
| `VM_GIT_REPO` | `git@github.com:Alkerm/stream-hacka.git` | Either HTTPS (requires PAT) or SSH (requires deploy key on VM) |
| `VM_GIT_REF` | `feat/pos-analyst` (initially), then `main` | Default ref when not overridden by dispatch input |

### Environments

Protect `deploy.yml` with a GitHub **environment** named `production`:
- Optional required reviewer
- Scope secrets so only the `production` environment can read `MINIMAX_API_KEY` and `POS_API_KEY`

## Promotion model

```
  feat/*  ──push──▶  CI (parse + build)  ──PR & merge──▶  main
  main    ──tag pos-analyst-vX.Y.Z──▶  deploy  ──▶  Vast VM
```

- Day-to-day: merge to `main`, manually dispatch `deploy` when you want it live.
- Release hygiene: tag `pos-analyst-v0.1.0` etc.; the deploy workflow picks up the tag automatically and deploys exactly that commit.

## Rollbacks

Fastest: re-run `deploy.yml` with `git_ref` set to the previous tag or commit SHA. The VM will `git reset --hard` to that ref and rebuild, which restores the exact image that commit produced (pinned `requirements.txt` + lockable Docker base image).

## What CI does NOT do yet

- End-to-end job test (needs a real MiniMax key and is expensive). Add as a nightly workflow if needed, gated on a separate `MINIMAX_API_KEY_CI` secret with a small monthly cap.
- Auto-provisioning of a fresh VM. Provisioning still goes through `scripts/deploy_vast.py up` (local or runner with VAST_API_KEY). The deploy workflow is deliberately scoped to redeploying onto an **already-provisioned** VM — this is the high-frequency operation.
- Image registry push. If you want images cached between runners and the VM: add a `login → push` step to Docker Hub or GHCR, then `docker pull` on the VM instead of rebuilding. Current setup rebuilds on the VM for self-containment.

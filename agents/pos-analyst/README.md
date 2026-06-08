# POS Financial Analyst

Autonomous financial-analyst agent for restaurant/café point-of-sale data. Takes transaction CSVs + a free-text business context over HTTP, runs a ReAct loop with Python in a sandboxed Docker sibling, and returns a non-technical business report grounded in computed findings.

Analyst model: **MiniMax-M2.7** (OpenAI-compatible endpoint).
Runtime: **Vast.ai VM** + docker-compose, sibling-container sandbox per code-exec step.

## Where things live

| Path | Purpose |
|---|---|
| [SKILL.md](SKILL.md) | Skill spec + lifecycle + component map |
| [agents/pos_analyst.yaml](agents/pos_analyst.yaml) | Model + prompt entry points |
| [references/](references/) | Methodology, benchmarks, report structure, memory schema, vast workflow |
| [scripts/](scripts/) | FastAPI service, agent loop, sandbox runner, deploy script |
| [docs/MINIMAX_SETUP.md](docs/MINIMAX_SETUP.md) | Get the API key + variant selection |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Zero-to-live runbook |
| [docs/CICD.md](docs/CICD.md) | CI + deploy workflow contract |

## Quickstart

```bash
# 1. Scout a VM
python3 scripts/deploy_vast.py scout

# 2. Rent + deploy
export VAST_API_KEY=...
export MINIMAX_API_KEY=sk-...
export POS_API_KEY=$(openssl rand -hex 24)
python3 scripts/deploy_vast.py up --pos-api-key "$POS_API_KEY"

# 3. Submit a job
curl -H "X-API-Key: $POS_API_KEY" \
     -F "context=<brief>" -F "files=@transactions.csv" \
     http://<VM_HOST>:8080/jobs
```

Debug inspection endpoints:

```bash
curl -H "X-API-Key: $POS_API_KEY" http://<VM_HOST>:8080/jobs/<job_id>/trace
curl -H "X-API-Key: $POS_API_KEY" http://<VM_HOST>:8080/jobs/<job_id>/steps
curl -H "X-API-Key: $POS_API_KEY" http://<VM_HOST>:8080/jobs/<job_id>/steps/<step_id>
```

Full details in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Strema sample dataset

For the generated multi-file daily financial portfolio dataset in `D:\downloads\Strema\generated_dataset_v2`, use:

- [examples/strema_portfolio_context.md](examples/strema_portfolio_context.md)
- [examples/submit_strema_job.ps1](examples/submit_strema_job.ps1)

The helper uploads `merchants.csv`, `sales_daily.csv`, `payments_daily.csv`, `bank_daily.csv`, and `obligations.csv` as a single job to the running API.

# MiniMax setup

The POS analyst talks to MiniMax over the OpenAI-compatible endpoint. This doc covers: get the key, verify it works, wire it into the stack.

## 1. Get the key

1. Create an account at <https://www.minimax.io/> (global) — **not** minimax.chat or the CN-only console.
2. Console → **API Keys** → create a key. Copy it once; MiniMax does not show the full key again.
3. Add a billing method. M2.7 costs **$0.30 / M input tokens + $1.20 / M output tokens**. Typical single POS job is ~5–15 M total tokens across all phases → about $6–$20 per full report at non-trivial dataset sizes. The first `$1` of credit is plenty for a smoke test.

## 2. Verify the key locally

```bash
export MINIMAX_API_KEY=sk-...

python3 - <<'PY'
from openai import OpenAI
c = OpenAI(api_key="$MINIMAX_API_KEY".replace("$MINIMAX_API_KEY",""), base_url="https://api.minimax.io/v1")
import os
c = OpenAI(api_key=os.environ["MINIMAX_API_KEY"], base_url="https://api.minimax.io/v1")
r = c.chat.completions.create(
    model="MiniMax-M2.7",
    messages=[{"role":"user","content":"Return exactly the string: OK"}],
    max_tokens=10,
)
print(r.choices[0].message.content)
PY
```

Expected: `OK` (with maybe punctuation). Anything else — key is wrong or billing isn't set up.

## 3. Variant selection

| Env var | Value | When to use |
|---|---|---|
| `POS_MODEL_ID` | `MiniMax-M2.7` (default) | Best quality. Reasoning, planning, code-writing agent loop. |
| `POS_MODEL_ID` | `MiniMax-M2.7-highspeed` | ~3× faster, identical results per MiniMax docs. Prefer when you need snappier end-to-end wall time. |
| `POS_REPORT_MODEL_ID` | either of the above | Override only the final report-writing call. Useful if you want M2.7 for reasoning and -highspeed for the long report synthesis. |

## 4. Tuning knobs

| Env var | Default | Effect |
|---|---|---|
| `POS_LLM_TIMEOUT` | 180 | Per-request timeout (seconds). Raise if long reports time out. |
| `POS_LLM_RETRIES` | 4 | Exponential backoff on 429/5xx. |
| `POS_LLM_TEMP` | 0.2 | Low temp keeps the agent deterministic. Raise for more creative report prose (0.4 max recommended). |
| `POS_MAX_CODE_STEPS` | 80 | Cap on sandbox `run_python` calls per job. |

## 5. Where it gets read

- Local dev: `scripts/docker-compose.yml` reads `MINIMAX_API_KEY` from the shell environment (or an `.env` file next to it).
- CI/CD (GitHub Actions): stored as the repo secret `MINIMAX_API_KEY`, passed to the VM's `.env` by the `deploy` workflow.
- On the Vast VM: lives in `${VM_REMOTE_DIR}/pos-analyst/scripts/.env` with `chmod 600`. Never echo it into logs; the compose file references it by name only.

## 6. Rotating the key

1. MiniMax console → API Keys → create a new key.
2. Update the `MINIMAX_API_KEY` repo secret on GitHub.
3. Re-run the `pos-analyst deploy` workflow. It rewrites `.env` and does `docker compose up -d`, which rolls the API container. In-flight jobs finish on the old key; new jobs pick up the new one.
4. Revoke the old key in the MiniMax console.

## 7. Cost guardrails worth setting

- **MiniMax side**: set a monthly spend cap in the console.
- **Agent side**: lower `POS_MAX_CODE_STEPS` to 40 for cost-sensitive runs. The agent is told the cap and spends more deliberately.
- **Surveillance**: `GET /jobs/{id}/trace` lists every tool call with timing; sum them to get a per-job token estimate.

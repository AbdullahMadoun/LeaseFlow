# 05 — Local Dev Setup

## Prerequisites

- Node 20+
- Python 3.12 (for the backend if you need to boot it)
- Docker (only if you want the existing pos-analyst engine too — not required for frontend work)

## Boot the backend locally

```bash
cd /Users/abdulrazzak/Madoun_Shit/stream-hacka/leaseflow

# One-time venv setup (already exists at /Users/abdulrazzak/Madoun_Shit/leaseflow/.venv)
# If missing:
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Boot the orchestrator
set -a && . /Users/abdulrazzak/Madoun_Shit/.env.leaseflow && set +a
export RISK_SNAPSHOT_ON_STARTUP=false
export RISK_SNAPSHOT_INTERVAL_S=0
export LEASEFLOW_DEV_FIXTURES=true     # mounts /dev/generate-fixtures
export BIND_PORT=8000

/Users/abdulrazzak/Madoun_Shit/leaseflow/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --reload

# Verify
curl http://127.0.0.1:8000/health
```

## Boot the frontend

```bash
cd /Users/abdulrazzak/Madoun_Shit/stream-hacka/frontend

# First-time only
cp .env.example .env.local
# Edit .env.local — paste values from /Users/abdulrazzak/Madoun_Shit/.env.leaseflow

npm install
npm run dev   # serves at http://localhost:5173
```

Your `.env.local`:
```
VITE_SUPABASE_URL=https://gbdnlnoqkdislrhvfxol.supabase.co
VITE_SUPABASE_ANON_KEY=<paste from .env.leaseflow: SUPABASE_ANON_KEY>
VITE_VAST_AI_URL=http://localhost:8000
VITE_STORAGE_BUCKET=loan-documents
```

---

## Test end-to-end (without the frontend)

Use the backend's e2e test script. It creates a user, loan, docs, runs the
pipeline, asserts outputs. Kills the user on exit.

```bash
cd /Users/abdulrazzak/Madoun_Shit/stream-hacka/leaseflow
set -a && . /Users/abdulrazzak/Madoun_Shit/.env.leaseflow && set +a
export RISK_SNAPSHOT_ON_STARTUP=false
export LEASEFLOW_DEV_FIXTURES=true
export BIND_PORT=8765
export BASE_URL=http://127.0.0.1:8765

# In one terminal: boot
/Users/abdulrazzak/Madoun_Shit/leaseflow/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8765

# In another: run
/Users/abdulrazzak/Madoun_Shit/leaseflow/.venv/bin/python tests/e2e_payments.py
```

Expect 60-90s runtime. Output shows Phase A extractions, Phase B dims, Phase C
synthesis, installment generation, webhook simulation.

---

## One-click test data for the frontend

Once backend is up with `LEASEFLOW_DEV_FIXTURES=true`, you can populate a
loan with realistic fake docs in one call. Useful for iterating on the UI
without real merchant data.

```ts
// From your frontend, after creating a loan:
await fetch(`${import.meta.env.VITE_VAST_AI_URL}/dev/generate-fixtures`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ loan_id: loan.id }),
});
// Now /analyze/start will have 4 realistic docs to work with.
```

Or via curl:
```bash
curl -X POST http://localhost:8000/dev/generate-fixtures \
  -H "Content-Type: application/json" \
  -d '{"loan_id": "<paste loan uuid>"}'
```

---

## Promoting a test user to admin

All new signups land as `merchant`. To access admin routes, manually flip the role:

```sql
-- In the Supabase dashboard SQL editor
UPDATE profiles SET role='admin' WHERE id = '<auth user id>';
```

Or via the Supabase CLI:
```bash
# Find your user id first
curl -H "apikey: <service_key>" -H "Authorization: Bearer <service_key>" \
  "https://gbdnlnoqkdislrhvfxol.supabase.co/auth/v1/admin/users" | jq
```

---

## Simulating a Stream payment (for webhook testing)

The real Stream flow: merchant clicks Pay now → Stream checkout → Stream
webhooks our backend. For dev you can simulate the webhook directly:

```bash
# Grab a subscription_cycle / installment link_id from the installments table
# (schema changed during backend refactor — see 06_GOTCHAS.md)

curl -X POST http://localhost:8000/webhooks/stream \
  -H "Content-Type: application/json" \
  -H "X-Stream-Signature: dev" \
  -d '{
    "event": "payment.completed",
    "link_id": "<from installments table>",
    "amount_sar": 4791.67,
    "paid_at": "2026-05-01T09:00:00Z",
    "payment_method": "mada",
    "transaction_ref": "dev_test_001"
  }'
```

With `STREAM_WEBHOOK_SECRET=""` (default for demo), signature verification
is bypassed. Set it to a real value for prod.

---

## Useful curl snippets

```bash
# Backend health
curl http://localhost:8000/health

# Start analysis on a loan
curl -X POST http://localhost:8000/analyze/start \
  -H "Content-Type: application/json" \
  -d '{"loan_id": "<uuid>"}'

# Poll status
curl http://localhost:8000/analyze/status/<uuid>

# Fetch full audit trace (admin feature)
curl http://localhost:8000/analyze/trace/<uuid>

# Classify a document
curl -X POST http://localhost:8000/documents/classify \
  -H "Content-Type: application/json" \
  -d '{"storage_path": "<merchant_id>/<loan_id>/bank_statement/<uuid>.pdf"}'

# Current risk snapshot
curl http://localhost:8000/risk/current
```

---

## Browser-testing the frontend

Use the `as-browser-testing-with-devtools` skill. Open the frontend at
`http://localhost:5173`, exercise each phase, check console + network tabs
for errors. Critical things to verify:

- Supabase Auth redirects work (signup → profile trigger → role route)
- Storage upload hits the right path prefix (403 = wrong prefix)
- Realtime channels connect (look for `phx_reply`/`postgres_changes` frames)
- REST calls to orchestrator don't CORS-fail

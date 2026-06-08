# Re-seeding the 3 demo merchants

If the demo data gets corrupted (someone accidentally approves Awful, the
demo was DB-wiped, etc.), here's how to put it back.

## The seed script

`leaseflow/scripts/seed_demo.py` is idempotent:

- finds + deletes any existing auth user with the persona's email
- cascades merchants → loans → documents deletion
- creates fresh auth user, merchant, loan
- generates 4 docs with persona-specific parameters (monthly revenue,
  volatility, bounces, etc. — tuned so Qahwa has strong numbers and Awful
  has weak ones)
- uploads to Supabase Storage + inserts documents rows
- POST /analyze/start on the deployed backend
- polls /analyze/status until synthesis=done
- records the final decision

Takes ~5 minutes (one full pipeline run × 3 merchants).

## How to run

From the VM (simplest):

```sh
ssh -p 35218 root@159.48.242.1
cd /opt/leaseflow
# copy script into running container (not baked into the image)
docker exec leaseflow-orchestrator mkdir -p /srv/scripts /srv/handoff
docker cp leaseflow/scripts/seed_demo.py leaseflow-orchestrator:/srv/scripts/
docker compose exec -T \
  -e BASE_URL=http://127.0.0.1:8000 \
  -e SEED_PASSWORD=demo123! \
  orchestrator python /srv/scripts/seed_demo.py
```

From local (if you want to target the public URL):

```sh
cd stream-hacka/leaseflow
set -a && . /Users/abdulrazzak/Madoun_Shit/.env.leaseflow && set +a
BASE_URL=https://leaseflow.imdad.website \
SEED_PASSWORD=demo123! \
  .venv/bin/python scripts/seed_demo.py
```

## What to expect

The script prints a per-persona section ending in:

```
  ✓  expected=approved  got=approved
```

If the checkmark is a ⚠, the LLM flipped a decision in a way we didn't
expect — usually benign (MiniMax being more conservative on synthetic data)
but worth investigating for demo reliability.

## Making demo subscriptions actually work on Stream

`.demo` and `.test` TLDs are blocked by Stream v2's consumer creation
("reserved TLD"). To get real Stream pay-now links on Qahwa's installments:

1. Edit `leaseflow/scripts/seed_demo.py` — change the `email` fields in
   PERSONAS from e.g. `qahwa@leaseflow.demo` to `qahwa+demo@gmail.com`
   (or any real-TLD address you control). Gmail aliases work fine.
2. Re-run the seed.

The Stream consumer step will succeed this time; installments will have
real `stream_payment_url` values the merchant UI can link to.

Decisions themselves (approved / denied / manual_review) don't depend on
the email at all — only the Stream billing chain does.

## If the reseed fails with HTTP 422

That's `/analyze/start` rejecting the loan because required documents are
missing. Two causes:

1. **Backend is behind a stale git state** — redeploy it:
   ```sh
   ssh -p 35218 root@159.48.242.1 'cd /opt/leaseflow && git pull origin main && docker compose up -d --build orchestrator'
   ```
2. **risk_policies.rules.required_documents is misconfigured.** Check:
   ```sql
   SELECT rules->'required_documents' FROM risk_policies ORDER BY effective_from DESC LIMIT 1;
   ```
   Should be `{"all_of": ["invoice"], "any_of": [["bank_statement"], ["financial_statement"]]}`.
   If different, the seed needs matching doc_types.

## If a persona's outcome doesn't match

The 3 CR numbers in `seed_demo.py` are tuned to the SIMAH stub's hash
function:
- `1010000000` → credit 787, defaults 0 (for Qahwa → approved)
- `1010000085` → credit 470, defaults 1 (for Awful → hard-floor deny)
- `1010000010` → credit 639, defaults 0 (for Iffy → borderline review)

If SIMAH's stub algorithm changes, these CRs may produce different
outputs. Re-find working CRs by running this snippet:

```py
import hashlib
def simah(cr):
    s = int(hashlib.sha256(cr.encode()).hexdigest()[:8], 16)
    return {"credit_score": 450 + (s % 400), "defaults": 1 if s % 20 == 0 else 0}

# then loop 1010000000..1010999999 until you find CRs matching desired outcomes
```

The generator params in PERSONAS also matter — Qahwa's `gen_params.bank`
sets monthly_revenue_target=95000 which drives DSCR → financial score.
Tune those if you need to shift a persona up/down.

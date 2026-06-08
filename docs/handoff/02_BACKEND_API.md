# 02 — Backend API Reference

Complete reference. For deeper payload shapes see `../leaseflow/docs/API_CONTRACT.md`
(the authoritative spec). This file is the concise cheatsheet.

There are **two backend surfaces** the frontend talks to:

1. **Supabase directly** — via `@supabase/supabase-js` with the anon key. RLS
   enforces what each user can read/write. Auth, DB inserts, file uploads,
   Realtime subscriptions.
2. **LeaseFlow REST API** — via `fetch` to the orchestrator. Default URL
   `http://localhost:8000`. Triggers the analysis pipeline, classifies docs,
   runs admin operations.

## Environment values

```js
// Put these in frontend/.env.local (Vite reads VITE_* at build):
VITE_SUPABASE_URL=https://gbdnlnoqkdislrhvfxol.supabase.co
VITE_SUPABASE_ANON_KEY=<from /Users/abdulrazzak/Madoun_Shit/.env.leaseflow>
VITE_VAST_AI_URL=http://localhost:8000         # orchestrator
VITE_STORAGE_BUCKET=loan-documents
```

Service keys (`SUPABASE_SERVICE_KEY`, `STREAM_API_SECRET`, `MINIMAX_API_KEY`)
NEVER go in the browser. Only the anon key.

---

## Supabase Auth

```ts
// signup
const { error } = await sb.auth.signUp({
  email, password,
  options: { data: { display_name } },
});

// login
const { error } = await sb.auth.signInWithPassword({ email, password });

// who am I + role
const { data: profile } = await sb.from("profiles").select("role").single();
// route: admin → /admin, merchant → /merchant

// logout
await sb.auth.signOut();
```

On signup a DB trigger inserts a `profiles` row with `role='merchant'`.
Promoting to admin is manual (`UPDATE profiles SET role='admin' WHERE id=...`).

---

## Tables (what the frontend reads + writes)

### `profiles`
- Auto-created on signup by trigger. Don't INSERT from frontend.
- Read-only for role routing. Merchants can update `display_name` but not `role`.
- `SELECT role FROM profiles` → 'merchant' | 'admin'

### `merchants`
- One row per merchant user. INSERT once on first login.
- RLS: self SELECT + self UPDATE + self INSERT. `user_id` auto-fills from JWT —
  don't send it.
```ts
await sb.from("merchants").insert({
  business_name: "Qahwa Haneen",
  cr_number: "1010XXXXXX",
  google_maps_url: "https://maps.app.goo.gl/...",
  phone: "+966-...",
});
```

### `loans`
- Merchant creates with status='pending_analysis'. Don't set
  `decision_payload`, `approved_amount`, `status` beyond that — backend owns.
```ts
const { data: loan } = await sb.from("loans").insert({
  merchant_id: myMerchantId,
  amount_requested: 50000,
  item_description: "La Marzocco GB5 espresso machine",
  profit_rate: 0.15,
  repayment_months: 12,
  repayment_frequency: "monthly",    // or "weekly" / "biweekly" / "daily"
}).select().single();
```

### `documents`
- Merchant inserts after uploading to Storage.
```ts
await sb.from("documents").insert({
  loan_id,
  doc_type: "bank_statement",   // | "financial_statement" | "pos_data" | "invoice"
  storage_path: path,
});
```

### `dimension_results`
- Read-only for merchants. Written by backend. Subscribe via Realtime for live
  progress.

### `installments`
- Read-only for merchants (their own loans only). Contains Stream payment URLs.
- Subscribe via Realtime for live payment status updates.
```ts
await sb.from("installments")
  .select("*")
  .eq("loan_id", loanId)
  .order("installment_number");
```

### Admin-only tables (RLS: admin sees all; merchants see nothing)
- `risk_snapshots` — current + historical risk appetite
- `ai_traces` — full audit log of every LLM call
- `risk_policies` — decision rules
- `segments` — F&B benchmark catalog (all authenticated can SELECT)

---

## Supabase Storage

Bucket: `loan-documents` (private, 50MB max per file)

**Path convention (ENFORCED BY RLS — get it wrong, get 403):**
```
{merchant_id}/{loan_id}/{doc_type}/{uuid}.{ext}
```

```ts
async function uploadDoc(merchantId, loanId, docType, file) {
  const ext  = file.name.split(".").pop();
  const id   = crypto.randomUUID();
  const path = `${merchantId}/${loanId}/${docType}/${id}.${ext}`;
  const { error } = await sb.storage
    .from("loan-documents")
    .upload(path, file, { upsert: false });
  if (error) throw error;
  return path;
}
```

MIME types allowed: PDF, CSV, Excel, JSON, JPEG, PNG. Max 50MB per file.
Merchants can't UPDATE/DELETE uploaded files — only admins.

---

## Supabase Realtime

`REPLICA IDENTITY FULL` is set on `loans`, `dimension_results`, `installments`
— so `payload.new` contains the complete updated row. No re-SELECT needed.

```ts
// Merchant dashboard — watch own loans
sb.channel(`loans:${merchantId}`)
  .on("postgres_changes",
      { event: "*", schema: "public", table: "loans",
        filter: `merchant_id=eq.${merchantId}` },
      (payload) => updateLoan(payload.new))
  .subscribe();

// Loan detail — watch dim completion live
sb.channel(`dims:${loanId}`)
  .on("postgres_changes",
      { event: "*", schema: "public", table: "dimension_results",
        filter: `loan_id=eq.${loanId}` },
      (payload) => updateDim(payload.new))
  .subscribe();

// Payments — watch installment paid
sb.channel(`installments:${loanId}`)
  .on("postgres_changes",
      { event: "*", schema: "public", table: "installments",
        filter: `loan_id=eq.${loanId}` },
      (payload) => updateInstallment(payload.new))
  .subscribe();

// Admin dashboard — all loans (no filter; admin RLS allows all)
sb.channel("admin:loans").on("postgres_changes",
  { event: "*", schema: "public", table: "loans" },
  (p) => adminFeed(p.new)).subscribe();
```

---

## REST API — the orchestrator (`VITE_VAST_AI_URL`)

No auth on the API itself. CORS is open for dev; set `CORS_ORIGINS` to your
deployed frontend origin in prod.

### `GET /health`
Liveness + Supabase reachability check.

### `POST /analyze/start`
Kicks off the 3-phase pipeline for a loan.

**Request:**
```json
{ "loan_id": "d7da3948-..." }
```

**Responses:**
- `200` — `{status: "started" | "already_running" | "already_complete", loan_id, registered_dimensions: [...]}`
- `404` — loan not found
- `422` — required documents missing:
```json
{
  "detail": {
    "error": "required_documents_missing",
    "missing_all_of": ["invoice"],
    "missing_any_of": [["bank_statement"], ["financial_statement"]],
    "uploaded_types": ["invoice"]
  }
}
```

Idempotent: safe to call twice.

### `GET /analyze/status/{loan_id}`
Snapshot of pipeline progress. Prefer Realtime; use this as the fallback when
the websocket drops.

**Response:**
```json
{
  "loan_id": "...",
  "loan_status": "analyzing" | "manual_review" | "approved" | "denied",
  "synthesis_status": "pending" | "running" | "done" | "error",
  "dimensions": [
    { "dimension": "pos", "status": "done", "score": 72, "confidence": 0.85,
      "narrative": "...", "error_message": null, "updated_at": "..." }
  ],
  "documents": [
    { "id": "...", "doc_type": "bank_statement", "analysis_status": "done",
      "extractor_schema_version": "v1" }
  ],
  "timing": {
    "submitted_at": "2026-04-16T...",
    "started_at": "2026-04-16T...",
    "completed_at": "2026-04-16T...",
    "submission_to_decision_s": 87.23,
    "pipeline_duration_s": 78.45
  }
}
```

### `GET /analyze/trace/{loan_id}` (admin-only by convention)
Full audit timeline — every LLM call + rule fire + aggregation + reconcile +
extraction event for a loan. Returns `ai_traces` rows sorted by `created_at`
plus all `documents.analysis_report` contents.

**Response:**
```json
{
  "loan_id": "...",
  "traces": [
    {
      "id": "...",
      "stage": "extract_bank_statement",
      "dimension": "financial_docs",
      "kind": "llm_call" | "rule" | "aggregation" | "reconcile" | "extraction",
      "prompt": { "system": "...", "user": "..." },
      "response_raw": { "content": "<think>...</think>{...}", "finish_reason": "stop", "usage": {...} },
      "parsed": { ... },
      "model": "MiniMax-M2.7",
      "duration_ms": 5385,
      "error": null,
      "created_at": "..."
    }
  ],
  "documents": [
    { "id": "...", "doc_type": "bank_statement", "storage_path": "...",
      "analysis_status": "done", "analysis_report": { ... full extractor output } }
  ]
}
```

### `POST /documents/classify`
Fast (~200ms) fitz keyword classifier. Called after upload, before creating
the `documents` row, so the UI can auto-select `doc_type`.

**Request:**
```json
{ "storage_path": "{merchant_id}/{loan_id}/_pending/{uuid}.pdf" }
```

**Response:**
```json
{
  "doc_type": "bank_statement" | "financial_statement" | "pos_data" | "invoice" | "unknown",
  "confidence": 0.92,
  "filename": "bank_statement.pdf",
  "signals": { "bank_statement": ["opening balance", "IBAN", "Al Rajhi"] },
  "snippet": "first 400 chars of extracted text",
  "page_count": 7,
  "raw_scores": { "bank_statement": 22, "financial_statement": 0, "invoice": 0 }
}
```

`doc_type="unknown"` means `confidence < 0.55` — prompt the user to pick.

### `POST /dev/generate-fixtures` (dev-only, env-gated)
Generates fake bank statement + financial statement + POS CSV + invoice for a
loan, uploads them to Storage, inserts `documents` rows. Only mounted when
`LEASEFLOW_DEV_FIXTURES=true`. Use this for one-click test populate.

**Request:**
```json
{ "loan_id": "...", "include": ["bank_statement", "financial_statement", "pos_data", "invoice"] }
```

**Response:**
```json
{
  "loan_id": "...",
  "generated": [
    { "doc_type": "bank_statement", "document_id": "...", "storage_path": "...", "size_bytes": 7552 },
    ...
  ]
}
```

### `GET /risk/current`
Returns latest `risk_snapshots` row. Admin banner.

### `POST /risk/snapshot`
Force a fresh snapshot now. Admin action.

### `POST /webhooks/stream`
Inbound from Stream. Signature verified with HMAC-SHA256 against
`STREAM_WEBHOOK_SECRET`. On a cycle-paid event: marks the matching
`installments` row paid, bumps `loans.amount_paid`, fires receipt email.
Idempotent (re-deliveries are no-ops).

> **In flight** (as of this handoff being written): the backend is migrating
> from per-installment payment links to one Stream **subscription per loan**
> using Stream App v2 (`https://stream-app-service.streampay.sa`). See
> `06_GOTCHAS.md` for the full story. The webhook event shape may change
> from `payment.completed` to a subscription cycle event. Frontend does not
> call the webhook directly — it just observes `installments.status` flipping
> to `paid` via Realtime. The exact webhook body is a backend-internal detail.

**Frontend doesn't call this** — Stream does. For dev testing, peek at
`leaseflow/app/routers/payments.py` for the current expected body shape:
```bash
curl -X POST http://localhost:8000/webhooks/stream \
  -H "Content-Type: application/json" \
  -H "X-Stream-Signature: dev" \
  -d '{...body matching current backend expectation...}'
```

### `POST /installments/{id}/regenerate-link`
Admin only. If a Stream link expired, regenerate it. Returns new link details.
(May be deprecated in the subscription model — subscriptions don't expire
mid-cycle the way one-off links do.)

---

## Error format

All 4xx / 5xx responses from the orchestrator are FastAPI defaults:
```json
{ "detail": "string" }
```
…except `/analyze/start` 422 which returns a structured detail object (see above).

---

## RLS cheat sheet (what the anon key CAN do)

| Table | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| `profiles` | self + admin | (trigger only) | self (not role) | admin |
| `merchants` | self + admin | self | self + admin | admin |
| `loans` | own + admin | own, `status='pending_analysis'` only | admin only | admin |
| `documents` | own loans + admin | own loans | admin | admin |
| `dimension_results` | own loans + admin | admin (backend) | admin (backend) | admin |
| `installments` | own loans + admin | admin (backend) | admin (backend) | admin |
| `risk_snapshots` | admin | admin (backend) | admin | admin |
| `risk_policies` | admin | admin | admin | admin |
| `ai_traces` | admin | admin (backend) | admin | admin |
| `segments` | all authenticated | admin | admin | admin |
| `storage.objects` | own prefix + admin | own prefix | admin | admin |

"Backend" writes bypass RLS because the orchestrator uses the service_role key.

---

## TypeScript types — generate these

Run against the live schema:
```bash
npx supabase gen types typescript --project-id gbdnlnoqkdislrhvfxol > frontend/src/lib/database.types.ts
```

Then import `Database` for strongly-typed queries:
```ts
import { createClient } from '@supabase/supabase-js';
import type { Database } from './database.types';

const sb = createClient<Database>(url, anonKey);
```

---

## What you should NOT try to do from the frontend

- Write to `dimension_results`, `ai_traces`, `installments`, `risk_snapshots`,
  `risk_policies` — all admin+backend only.
- Update `loans.status`, `loans.decision_payload`, `loans.approved_amount` —
  backend owns (or admin overrides).
- Generate Stream payment links directly — backend does this on approval.
- Compute DSCR, monthly payment, or any financial math — read from backend.

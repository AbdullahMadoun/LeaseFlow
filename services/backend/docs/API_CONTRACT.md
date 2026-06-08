# LeaseFlow — Frontend ↔ Backend Contract

This document is the authoritative spec for what the frontend talks to and
where. There are two distinct surfaces:

1. **Supabase directly** — auth, DB inserts, file uploads, Realtime subscriptions.
2. **LeaseFlow REST API** — analysis pipeline triggers and status reads.

The frontend uses `@supabase/supabase-js` v2 with the anon key for everything
under (1). Calls to (2) go to the orchestrator's public base URL.

## The pipeline (what `/analyze/start` kicks off)

```
Phase A — document extraction      (one task per uploaded document)
  Each document → fitz (PDF) or pandas (CSV) → LLM extractor →
  documents.analysis_report populated with a typed report (shape
  depends on doc_type — see "Document schemas" below)

Phase B — dimension fan-out         (5 dims in parallel)
  Financial + POS aggregators READ documents.analysis_report and combine
  SIMAH + Sentiment + Industry run natively (external data)
  Each writes to dimension_results, each LLM call to ai_traces

Phase C — expert synthesis          (single winner after B completes)
  Deterministic scorer + hard floors + LLM guardrail → decision_payload
```

Every LLM call in every phase writes a row to `ai_traces` (admin-only
read). For the admin timeline view, call `GET /analyze/trace/{loan_id}`.

---

## Environment variables the frontend needs

```js
// config.js — include on every page before other scripts
window.LEASEFLOW_CONFIG = {
  SUPABASE_URL:       "https://gbdnlnoqkdislrhvfxol.supabase.co",
  SUPABASE_ANON_KEY:  "eyJhbGciOi...",                      // safe to ship
  VAST_AI_URL:        "https://<vast-host>:8000",           // orchestrator
  STORAGE_BUCKET:     "loan-documents",
};
```

Service keys must NEVER ship to the browser.

---

## Auth

Supabase Auth email+password. On signup a `profiles` row is auto-created with
`role='merchant'`. Admins are flipped to `role='admin'` manually (out-of-band).

```js
// signup
await supabase.auth.signUp({ email, password, options: { data: { display_name } } });

// login
const { data, error } = await supabase.auth.signInWithPassword({ email, password });

// determine role after login
const { data: profile } = await supabase.from("profiles").select("role").single();
if (profile.role === "admin") location.href = "/admin/dashboard.html";
else                           location.href = "/merchant/dashboard.html";
```

Your JWT is automatically attached to every subsequent supabase-js call.

---

## Database tables and what the frontend does with each

### `profiles`
Auto-created on signup. Read-only for role-based routing. Don't INSERT — the
trigger does it.

### `merchants`
One row per merchant user. Must be created once on first login before any loans.

```js
await supabase.from("merchants").insert({
  business_name:   "Qahwa Haneen",
  cr_number:       "1010XXXXXX",
  google_maps_url: "https://maps.app.goo.gl/...",
  phone:           "+966-...",
});
```

RLS: merchant can see + update their own row only. `user_id` is auto-filled
from the JWT — you don't pass it.

Backend-managed exact Google place identity may also be persisted on the same
row after a successful review scrape:
- `google_place_id`
- `google_place_url`
- `google_place_title`
- `google_place_address`
- `google_place_resolved_at`

These fields are used so later underwriting runs can reuse the exact branch
identity instead of fuzzy-matching the brand name again.

### `loans`
Created by merchant on submit. **Do not set** `status`, `synthesis_status`,
`decision_payload`, `approved_amount`, or `monthly_payment` — the backend
owns those columns.

```js
const { data: loan } = await supabase.from("loans").insert({
  merchant_id:      <my merchant id>,
  amount_requested: 50000,
  item_description: "La Marzocco GB5 espresso machine",
  invoice_url:      null,    // optional, set after upload
  profit_rate:      0.15,    // default, don't change unless you know
  repayment_months: 12,      // default
}).select().single();
```

RLS: merchants see their own loans; admins see all.

After insert, the loan is in `status='pending_analysis'`. You upload docs next,
then call `/analyze/start`.

### `documents`
One row per uploaded file. `doc_type` drives which dim will run:

| doc_type             | triggers dim     | typical file          |
|----------------------|------------------|-----------------------|
| `bank_statement`     | `financial_docs` | PDF or CSV            |
| `financial_statement`| `financial_docs` | PDF                   |
| `pos_data`           | `pos`            | CSV / Excel export    |
| `invoice`            | (context only)   | PDF or image          |

Merchants without POS data simply don't upload a `pos_data` doc → POS dim is
skipped, other dims still run.

### `dimension_results`
Read-only for merchants and admins. Written by the backend. Subscribe via
Realtime to show progressive dim completion.

### `risk_snapshots`
Admin-only read. Written by the backend.

### `segments`
Read-only catalog. Admin UI may want to show benchmarks alongside the
industry dim output.

---

## Storage — uploading documents

**Bucket**: `loan-documents` (private).
**Path convention** (enforced by RLS):

```
{merchant_id}/{loan_id}/{doc_type}/{uuid}.{ext}
```

The first path segment MUST be the merchant's UUID. RLS verifies that segment
matches one of your merchant IDs. Violating the convention = 403.

```js
async function uploadDoc(merchantId, loanId, docType, file) {
  const ext  = file.name.split(".").pop();
  const id   = crypto.randomUUID();
  const path = `${merchantId}/${loanId}/${docType}/${id}.${ext}`;
  const { error } = await supabase.storage
    .from("loan-documents")
    .upload(path, file, { upsert: false });
  if (error) throw error;

  // Register the document
  await supabase.from("documents").insert({
    loan_id:      loanId,
    doc_type:     docType,
    storage_path: path,
  });
  return path;
}
```

Supported MIME types: `application/pdf`, `text/csv`, `text/plain`,
`application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`,
`application/json`, `image/jpeg`, `image/png`. Max size: 50 MB.

Merchants cannot UPDATE or DELETE uploaded files. Admins can.

---

## Realtime — the two subscriptions that matter

Subscribe to these two tables; you don't need to poll.

### Merchant dashboard — watch own loans

```js
const ch = supabase.channel(`loans:${merchantId}`)
  .on("postgres_changes",
      { event: "*", schema: "public", table: "loans",
        filter: `merchant_id=eq.${merchantId}` },
      (payload) => {
        // payload.new has the full updated row (REPLICA IDENTITY FULL is on)
        updateLoanUI(payload.new);
      })
  .subscribe();
```

### Loan detail page — watch this loan's dims (live progress)

```js
const ch = supabase.channel(`dims:${loanId}`)
  .on("postgres_changes",
      { event: "*", schema: "public", table: "dimension_results",
        filter: `loan_id=eq.${loanId}` },
      (payload) => {
        // Use payload.new.dimension + status + score + narrative
        updateDimCard(payload.new);
      })
  .subscribe();
```

### Admin dashboard — watch ALL loans

Same as merchant but drop the filter (admin RLS allows SELECT of everything).

---

## REST API — the orchestrator (VAST_AI_URL)

CORS: all origins open in dev; the deployment sets it to your frontend origin.
Auth: none on the API itself — the frontend is trusted because the heavy
operations (DB writes, decisions) happen server-side with the service key.
Do not forward user JWTs.

### `POST /analyze/start`

Kicks off the 5-dim pipeline for a loan.

**Request**
```json
{ "loan_id": "d7da3948-4014-43fe-985a-b9454a9025e6" }
```

**Response 200**
```json
{
  "status": "started" | "already_running" | "already_complete",
  "loan_id": "d7da3948-...",
  "registered_dimensions": ["financial_docs", "industry", "pos", "sentiment", "simah"]
}
```

Idempotent: calling twice is safe. The second call reports the current state.

**Errors**
- `404` — loan not found

### `GET /analyze/status/{loan_id}`

Snapshot of pipeline progress. You should prefer Realtime; this endpoint is
a fallback when the websocket drops.

**Response 200**
```json
{
  "loan_id": "d7da3948-...",
  "loan_status": "analyzing" | "manual_review" | "approved" | "denied",
  "synthesis_status": "pending" | "running" | "done" | "error",
  "dimensions": [
    {
      "dimension": "pos" | "financial_docs" | "simah" | "sentiment" | "industry",
      "status": "queued" | "processing" | "done" | "error" | "skipped",
      "score": 72,
      "confidence": 0.85,
      "narrative": "Stable weekday operation...",
      "error_message": null,
      "updated_at": "2026-04-16T..."
    }
  ],
  "documents": [
    {
      "id": "...",
      "doc_type": "bank_statement" | "financial_statement" | "pos_data" | "invoice",
      "analysis_status": "pending" | "processing" | "done" | "error",
      "extractor_schema_version": "v1"
    }
  ],
  "timing": {
    "submitted_at": "2026-04-16T09:11:32Z",
    "started_at": "2026-04-16T09:11:34Z",
    "completed_at": null,
    "submission_to_decision_s": null,
    "pipeline_duration_s": null
  },
  "analyst_jobs": {
    "single_business_fnb_analyst": {
      "job_key": "single_business_fnb_analyst",
      "eligible": true,
      "status": "queued" | "running" | "done" | "failed" | "error" | "skipped",
      "phase": "created" | "profile" | "context" | "plan" | "execute" | "validate" | "report" | null,
      "job_id": "j_...",
      "submitted_at": "2026-04-16T09:11:36Z",
      "updated_at": "2026-04-16T09:12:05Z",
      "report_ready": false,
      "file_names": ["merchant_profile.csv", "pos_daily.csv", "bank_monthly.csv"],
      "error": null
    }
  }
}
```

The backend starts this analyst job automatically after Phase A document extraction.
It is supplemental: the underwriting pipeline continues even if the analyst is slow or unavailable.

### `GET /analyze/trace/{loan_id}` (admin timeline)

Full audit trail for a loan — every LLM call, rule fire, aggregation,
reconciliation, and document extraction event, in chronological order.
Each LLM row includes the exact prompt sent, the raw response (with
`<think>` blocks), the parsed JSON, model, duration, and error if any.

**Response 200**
```json
{
  "loan_id": "...",
  "traces": [
    {
      "id": "...",
      "loan_id": "...",
      "document_id": "..." | null,
      "stage": "extract_bank_statement" | "dim_financial_reconcile" | "expert_synthesis" | ...,
      "dimension": "financial_docs" | null,
      "kind": "llm_call" | "rule" | "aggregation" | "reconcile" | "extraction",
      "prompt": { "system": "...", "user": "..." } | null,
      "response_raw": { "content": "...", "finish_reason": "stop", "usage": {...} } | null,
      "parsed": { ...dim-specific JSON } | null,
      "model": "MiniMax-M2.7" | null,
      "duration_ms": 5385,
      "error": null,
      "created_at": "2026-04-16T..."
    }
  ],
  "documents": [
    {
      "id": "...",
      "doc_type": "...",
      "storage_path": "...",
      "analysis_status": "done",
      "analysis_report": { ...full extractor output }
    }
  ]
}
```

Admin-only. The `ai_traces` table has RLS that only allows `is_admin()`
readers; our REST endpoint uses the backend service key and should be
fronted by admin check on the proxy or called via Supabase REST with
the admin JWT instead.

### `POST /analyze/analyst/start/{loan_id}`

Idempotently starts or reuses the supplemental single-business analyst job for a loan.
Useful if you want to re-trigger the agent outside the main underwriting pipeline.

### `GET /analyze/analyst/status/{loan_id}`

Returns the latest synced status snapshot for the supplemental analyst job.

### `GET /analyze/analyst/report/{loan_id}`

Returns the final analyst markdown report once the remote job reaches `done`.
Returns `409` while the remote job is still running.

### `POST /webhooks/stream`

Inbound webhook from Stream when a payment state changes. `X-Stream-Signature`
header verified via HMAC-SHA256 against `STREAM_WEBHOOK_SECRET` (accept-all
when unset for demo).

**Body** (stubbed shape — real Stream may differ)
```json
{
  "event": "payment.completed" | "payment.failed" | "payment.cancelled",
  "link_id": "stream_...",
  "amount_sar": 4791.67,
  "paid_at": "2026-05-16T09:00:00Z",
  "payment_method": "mada" | "visa" | "apple_pay",
  "transaction_ref": "txn_..."
}
```

On `payment.completed`: updates matching `installments` row (status='paid',
paid_at, paid_amount_sar, method, ref), bumps `loans.amount_paid`, fires
receipt email. Idempotent — re-delivery is safe.

### `POST /installments/{installment_id}/regenerate-link`

Admin action. Creates a fresh Stream payment link for an installment whose
previous link expired or otherwise needs replacement. Rejects with 409 if
the installment is already `paid`. Returns the new link details.

### Direct Supabase reads (no REST endpoint needed)

The frontend queries these via `supabase.from(...)` with RLS enforcement:

- `installments` — merchant sees own loan's installments, admin sees all.
  Realtime is enabled — subscribe on `loan_id=eq.<id>` to watch payment
  status flip when Stream confirms.
- `GET next installments for merchant`:
  ```js
  await supabase
    .from("installments")
    .select("*, loans!inner(merchant_id, item_description)")
    .eq("status", "pending")
    .order("due_date")
    .limit(10);
  ```
  RLS does the merchant filter automatically via the JOIN.

### `POST /documents/classify`

Fast keyword-heuristic classifier. Frontend calls this right after a doc is
uploaded to Storage, BEFORE creating the `documents` row, so it can auto-fill
`doc_type` and update the completeness widget. Keyword heuristics via fitz
(PDF) or CSV header sniffing — no LLM call, ~100-300ms.

**Request**
```json
{ "storage_path": "<merchant_id>/<loan_id>/<any-or-tmp>/<uuid>.<ext>" }
```

**Response 200**
```json
{
  "doc_type": "bank_statement" | "financial_statement" | "pos_data" | "invoice" | "unknown",
  "confidence": 0.0-1.0,
  "filename": "bank_statement.pdf",
  "signals": { "bank_statement": ["opening balance", "IBAN", "Al Rajhi"] },
  "snippet": "first 400 chars of extracted text (for UI preview)",
  "page_count": 7,
  "raw_scores": { "bank_statement": 22, "financial_statement": 0, "invoice": 0 }
}
```

`doc_type="unknown"` means confidence < 0.55 — prompt the user to pick manually.

Recommended merchant flow:
```
1. Upload file to Storage at a tentative path (e.g. {merchant_id}/{loan_id}/_pending/{uuid}.ext)
2. POST /documents/classify with that path
3. If confidence >= 0.55: frontend auto-selects doc_type, shows the classifier's snippet
   for confirmation, optionally moves the file to the canonical {doc_type}/ prefix
4. If "unknown": frontend prompts "What kind of document is this?" dropdown
5. Insert documents row with chosen doc_type
6. Completeness widget updates
```

Completeness rule (frontend):
- **Required**: 1× invoice AND at least 1 of (bank_statement, financial_statement)
- **Bonus**: pos_data (unlocks POS dim — show "POS analysis available" chip)

The backend extractors independently verify the doc_type at Phase A — if the
classifier was wrong, the extractor flags `not_a_X` in `meta.extraction_notes`
and the dim picks that up.

### `POST /dev/generate-fixtures` (dev-only)

Generates a full set of fake documents for a loan, uploads them to Storage,
and inserts `documents` rows so the pipeline has something to extract.

Only mounted when `LEASEFLOW_DEV_FIXTURES=true`. Frontend uses this for
one-click test-loan population.

**Request**
```json
{
  "loan_id": "...",
  "include": ["bank_statement", "financial_statement", "pos_data", "invoice"]
}
```
`include` is optional — default includes all 4.

**Response 200**
```json
{
  "loan_id": "...",
  "generated": [
    { "doc_type": "bank_statement",      "document_id": "...", "storage_path": "...", "size_bytes": 7552 },
    { "doc_type": "financial_statement", "document_id": "...", "storage_path": "...", "size_bytes": 3253 },
    { "doc_type": "pos_data",            "document_id": "...", "storage_path": "...", "size_bytes": 568892 },
    { "doc_type": "invoice",             "document_id": "...", "storage_path": "...", "size_bytes": 2480 }
  ]
}
```

### `GET /risk/current`

Returns the latest `risk_snapshots` row. Admin panel uses this to show the
current risk appetite banner.

### `POST /risk/snapshot`

Force a fresh risk snapshot (admin use only). Returns the new row.

### `GET /health`

Liveness + Supabase reachability, plus supplemental analyst reachability.
Useful for ops dashboards and deployment validation.

---

## End-to-end merchant flow

```js
// 1. User submits loan application
const loan = await createLoan({
  amount_requested: 50000,
  item_description: "La Marzocco GB5 espresso machine",
});

// 2. Upload each document (bank statement, invoice, etc.)
for (const { file, docType } of uploads) {
  await uploadDoc(merchantId, loan.id, docType, file);
}

// 3. Start analysis on the backend
const startResp = await fetch(`${LEASEFLOW_CONFIG.VAST_AI_URL}/analyze/start`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ loan_id: loan.id }),
}).then(r => r.json());

// 4. Subscribe to Realtime updates (dims + loan)
subscribeToLoanUpdates(loan.id);

// 5. Show "Application submitted, analysis in progress"
navigate(`/merchant/loan.html?id=${loan.id}`);
```

The `loan.html` page renders progress from the Realtime stream. When the
loan's `synthesis_status` transitions to `done`, read `decision_payload`
from the loan row and render the decision card.

---

## The `decision_payload` shape (what the loan detail page renders)

Admin panel shows the full payload. Merchant page shows only `final_decision`
+ `llm_response.reasoning`.

```json
{
  "schema_version": "v1",
  "deterministic_proposal": {
    "decision": "approve" | "deny" | "manual_review",
    "overall_score": 75.0,
    "amount_bounds": { "min": 40000, "max": 50000 },
    "rules_fired": ["overall_score>=70", "dscr_comfortable"],
    "per_dim": { "pos": 74, "financial_docs": 80, "simah": 70, "sentiment": 81, "industry": 62 },
    "risk_level": "low" | "medium" | "high"
  },
  "hard_floors_check": {
    "passed": true,
    "violations": []
  },
  "llm_response": {
    "decision": "approve",
    "confidence": 0.78,
    "recommended_amount": 48000,
    "reasoning": "Comfortable DSCR of 2.3× with stable revenue...",
    "risk_flags": ["sentiment_data_mocked"],
    "dimension_scores": { "pos": 74, "financial": 80, "credit": 70, "sentiment": 81, "industry": 62, "overall": 74 },
    "risk_level": "medium"
  } | null,
  "final_decision": {
    "status": "approved" | "denied" | "manual_review",
    "approved_amount": 48000 | null,
    "override_applied":
      "agreement" |
      "llm_downgrade" |
      "llm_upgrade_blocked" |
      "llm_primary" |
      "llm_unavailable_deterministic_only" |
      "hard_floor" |
      "none"
  },
  "registered_dimensions": ["pos", "financial_docs", "simah", "sentiment", "industry"],
  "dimension_scores": { "pos": 74, "financial_docs": 80, ... },
  "risk_snapshot_id": "abc123...",
  "generated_at": "2026-04-16T..."
}
```

For each dimension_result row, `result` is a full `DimensionOutput` (see
per-dim shapes below). The admin detail page is where all of this gets shown;
the merchant page just needs the decision + amount + reasoning.

---

## Admin manual override

When an admin approves/denies a loan manually:

```js
await supabase.from("loans").update({
  status:          "approved",   // or "denied"
  approved_amount: 48000,        // for approve only
}).eq("id", loanId);
```

RLS: only `is_admin()` can UPDATE loans. The DB webhook (task #13, deferred
for now) will fire an email notification to the merchant on this status
change. Until the webhook is deployed, email is sent only for
automated decisions.

---

## Dimension output shapes (for admin detail page)

Every `dimension_results.result` is a `DimensionOutput`:

```json
{
  "dimension": "pos" | "financial_docs" | "simah" | "sentiment" | "industry",
  "score": 0..100,
  "confidence": 0..1,
  "narrative": "1-2 sentence human-readable summary",
  "features": { /* dim-specific, see below */ },
  "flags": ["flag1", "flag2"],
  "dimension_version": "pos@stub-v1",
  "analyst_job_id": "j_..." | null
}
```

### POS features
```json
{
  "daily_revenue_avg_sar": 1200,
  "monthly_revenue_est_sar": 36000,
  "avg_ticket_sar": 45,
  "peak_hours": ["12:00-14:00", "19:00-22:00"],
  "seasonality": "weekend_heavy",
  "void_rate": 0.008,
  "refund_rate": 0.005,
  "cash_card_mix": { "cash": 0.18, "card": 0.82 },
  "trend_90d": "stable"
}
```

### Financial features
```json
{
  "monthly_revenue_avg_sar": 42000,
  "monthly_expenses_avg_sar": 28000,
  "monthly_net_avg_sar": 14000,
  "volatility": 0.18,
  "trend": "stable",
  "reconciliation": { "bank_vs_pos_revenue_delta_pct": 0.04, "consistent": true },
  "affordability": {
    "amount_requested": 50000,
    "profit_rate": 0.15,
    "repayment_months": 12,
    "total_due": 57500,
    "proposed_monthly_payment": 4791.67,
    "dscr": 2.92,
    "dscr_category": "comfortable" | "marginal" | "risky"
  }
}
```

### SIMAH features
```json
{
  "credit_score": 710,
  "active_facilities_count": 2,
  "active_facilities_total_sar": 85000,
  "defaults_count": 0,
  "payment_history": "excellent" | "good" | "fair" | "poor",
  "recent_inquiries_90d": 1,
  "simah_recommendation": "approve" | "caution" | "deny"
}
```

### Sentiment features
```json
{
  "google_rating": 4.4,
  "review_count": 312,
  "review_velocity_30d": 14,
  "last_review_days_ago": 3,
  "overall_sentiment": "positive" | "neutral" | "negative",
  "trend": "improving" | "stable" | "declining",
  "aspect_sentiment": {
    "food_quality": 0.82, "service": 0.61, "price": 0.45,
    "cleanliness": 0.78, "atmosphere": 0.71
  },
  "customer_profile": {
    "segments": ["families", "young_professionals"],
    "visit_reasons": ["quick_lunch", "weekend_dining"],
    "loyalty_signal": "moderate",
    "estimated_daily_foot_traffic_band": "80-120"
  },
  "red_flags": [],
  "business_identity_match": true,
  "scraped_successfully": false
}
```

### Industry features
```json
{
  "segment": "specialty_coffee",
  "segment_label": "Specialty coffee / counter-service café",
  "location": { "city": "Riyadh", "district": "Al Olaya" },
  "local_competition": {
    "similar_within_1km": 12,
    "avg_competitor_rating": 4.2,
    "density": "low" | "medium" | "high"
  },
  "segment_benchmarks": { /* same as segments table row */ },
  "macro": {
    "segment_growth_yoy": 0.08,
    "input_cost_trend": "stable" | "rising" | "falling",
    "regulatory_risk": "low" | "medium" | "high"
  }
}
```

---

## RLS summary (what the anon key can and can't do)

| Table               | SELECT              | INSERT               | UPDATE              | DELETE       |
|---------------------|---------------------|----------------------|---------------------|--------------|
| profiles            | self + admin        | trigger only         | self (not role)     | admin        |
| merchants           | self + admin        | self                 | self + admin        | admin        |
| loans               | own + admin         | own, status=pending  | admin only          | admin        |
| documents           | own loans + admin   | own loans            | admin               | admin        |
| dimension_results   | own loans + admin   | admin                | admin               | admin        |
| risk_snapshots      | admin               | admin (backend)      | admin               | admin        |
| segments            | all authenticated   | admin                | admin               | admin        |
| risk_policies       | admin               | admin                | admin               | admin        |
| ai_traces           | admin               | admin (backend)      | admin               | admin        |
| installments        | own loans + admin   | admin (backend)      | admin               | admin        |
| storage.objects     | own prefix + admin  | own prefix           | admin               | admin        |

"Backend" writes bypass RLS because the orchestrator uses the service_role key.

---

## Document extractor schemas (what populates `documents.analysis_report`)

Each `documents.analysis_report` is an instance of one of four Pydantic
models, matched by `doc_type`. These are the SAME shapes the fake-fixture
generators produce, so dev/demo = prod round-trip.

### `BankStatementReport` (`doc_type='bank_statement'`)
```json
{
  "doc_type": "bank_statement",
  "bank_name": "Al Rajhi Bank",
  "account_holder": "Qahwa Haneen",
  "iban_last4": "1234",
  "period_start": "2025-10-01",
  "period_end": "2026-03-31",
  "currency": "SAR",
  "monthly": [
    { "month": "2025-10", "revenue_sar": 84200, "expenses_sar": 61000,
      "net_sar": 23200, "txn_count": 312, "source_pages": [1] }
  ],
  "aggregates": {
    "monthly_revenue_avg_sar": 82100, "monthly_expenses_avg_sar": 59500,
    "monthly_net_avg_sar": 22600, "volatility": 0.18, "trend": "stable",
    "bounced_count": 0, "overdraft_events": 0
  },
  "flags": [],
  "meta": { "schema_version": "v1", "extractor_version": "v1",
            "confidence": 0.95, "low_confidence_fields": [], "extraction_notes": [],
            "source_filename": "bank_statement.pdf" }
}
```

### `FinancialStatementReport` (`doc_type='financial_statement'`)
```json
{
  "doc_type": "financial_statement",
  "company_name": "Qahwa Haneen",
  "period_start": "2025-01-01", "period_end": "2025-12-31",
  "balance_sheet": {
    "total_assets_sar": 430000, "total_liabilities_sar": 180000,
    "equity_sar": 250000, "current_assets_sar": 120000,
    "current_liabilities_sar": 60000, "source_pages": [1]
  },
  "income_statement": {
    "revenue_sar": 985000, "cogs_sar": 470000, "opex_sar": 295000,
    "net_profit_sar": 220000, "source_pages": [2]
  },
  "ratios": { "current_ratio": 2.0, "debt_to_equity": 0.72,
              "gross_margin": 0.523, "net_margin": 0.223 },
  "flags": [],
  "meta": { "confidence": 0.95, ... }
}
```

### `POSReport` (`doc_type='pos_data'`)
```json
{
  "doc_type": "pos_data",
  "period_start": "2026-01-16", "period_end": "2026-04-15",
  "currency": "SAR",
  "daily": [{ "date": "2026-01-16", "revenue_sar": 1820,
              "txn_count": 42, "avg_ticket_sar": 43.3 }],
  "aggregates": {
    "daily_revenue_avg_sar": 1850, "monthly_revenue_est_sar": 55500,
    "avg_ticket_sar": 44.1,
    "peak_hours": ["12:00-14:00", "19:00-21:00"],
    "seasonality": "weekend_heavy",
    "void_rate": 0.011, "refund_rate": 0.006,
    "cash_card_mix": { "cash": 0.18, "card": 0.82 },
    "trend_90d": "slightly_up"
  },
  "flags": [],
  "meta": { "confidence": 0.85, ... }
}
```

### `InvoiceReport` (`doc_type='invoice'`)
```json
{
  "doc_type": "invoice",
  "vendor_name": "Arabian Espresso Co.",
  "vendor_vat": "300123456700003",
  "invoice_number": "INV-202604-1234",
  "issue_date": "2026-04-10",
  "currency": "SAR",
  "line_items": [
    { "description": "La Marzocco GB5 espresso machine",
      "quantity": 1, "unit_price_sar": 43400, "total_sar": 43400 }
  ],
  "subtotal_sar": 43400, "vat_sar": 6510, "total_sar": 49910,
  "item_category": "coffee_equipment",
  "matches_requested_amount": true,
  "fraud_flags": [],
  "flags": [],
  "meta": { "confidence": 0.95, ... }
}
```

---

## Known limitations (demo scope)

- **SIMAH is stubbed** — deterministic fake output keyed off `cr_number` hash.
- **Google sentiment depends on Apify configuration** — the orchestrator now
  resolves a place from the merchant company name (or uses the provided Google
  Maps URL), scrapes Google-origin reviews through Apify, then runs MiniMax on
  the real review text. If Apify cannot match a place, the dim returns a
  low-confidence no-match result.
- **Google branch ambiguity is real** — company-name-only matching can be
  ambiguous for multi-branch brands. The resolver now fails closed on near-ties
  instead of guessing. Operational details and known issues are documented in
  `leaseflow/docs/GOOGLE_REVIEWS_ISSUES.md`.
- **Industry data is partly mocked** — segment classifier + narrative use
  real MiniMax calls; benchmarks come from the `segments` table (seeded from
  `pos-analyst/references/fnb-benchmarks.md`); local competition density is mock.
- **Pipeline durability**: FastAPI asyncio tasks. A mid-analysis container
  restart leaves the loan stuck in `analyzing`. Acceptable for demo.
- **No per-month payment tracking** — `amount_paid` is a single column, no
  schedule table.
- **Admin manual override email** — not yet wired (DB webhook deferred).
  Automated decisions do send email when `RESEND_API_KEY` is configured.
- **`/dev/generate-fixtures` is dev-only** — gated by `LEASEFLOW_DEV_FIXTURES=true`.
  Leave it off in production — the endpoint trusts the client and would let
  anyone populate test docs on a loan they don't own.

import { env } from "./env";

/**
 * Backend REST client — hits the LeaseFlow orchestrator (FastAPI) at
 * VITE_VAST_AI_URL. Response shapes are kept in sync with
 * leaseflow/docs/API_CONTRACT.md + the actual FastAPI routers.
 *
 * Cross-check map (endpoint → backend file):
 *   GET  /health                        → leaseflow/app/routers/health.py
 *   POST /documents/classify            → leaseflow/app/routers/documents.py
 *   POST /analyze/start                 → leaseflow/app/routers/analyze.py
 *   GET  /analyze/status/{id}           → leaseflow/app/routers/analyze.py
 *   GET  /analyze/trace/{id}            → leaseflow/app/routers/analyze.py (admin)
 *   POST /analyze/analyst/start/{id}    → leaseflow/app/routers/analyze.py
 *   GET  /analyze/analyst/status/{id}   → leaseflow/app/routers/analyze.py
 *   GET  /analyze/analyst/report/{id}   → leaseflow/app/routers/analyze.py
 *   GET  /risk/current                  → leaseflow/app/routers/risk.py
 *   POST /risk/snapshot                 → leaseflow/app/routers/risk.py (admin)
 *   POST /dev/generate-fixtures         → leaseflow/app/routers/dev.py
 *     (mounted only when LEASEFLOW_DEV_FIXTURES=true)
 */

class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = `${env.VAST_AI_URL}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  const text = await res.text();
  const body = text ? safeJson(text) : null;
  if (!res.ok) {
    throw new ApiError(res.status, body, `${res.status} ${res.statusText} @ ${path}`);
  }
  return body as T;
}

function safeJson(text: string): unknown {
  try { return JSON.parse(text); } catch { return text; }
}

// ---------- Response types (keep in sync with backend) ----------------------

export type HealthResponse = { status: string };

export type DocType =
  | "bank_statement"
  | "financial_statement"
  | "pos_data"
  | "invoice"
  | "unknown";

export type ClassifyResponse = {
  doc_type: DocType;
  confidence: number;               // 0.0 – 1.0
  filename: string;                 // last segment of storage_path
  signals: Record<string, unknown>; // heuristic signals the classifier matched on
  snippet: string;                  // first ~400 chars of extracted text
};

export type DimensionName =
  | "pos"
  | "financial_docs"
  | "simah"
  | "sentiment"
  | "industry";

export type DimensionStatus =
  | "queued"
  | "processing"
  | "done"
  | "error"
  | "skipped";

export type LoanStatus =
  | "pending_analysis"
  | "analyzing"
  | "manual_review"
  | "approved"
  | "denied";

export type SynthesisStatus = "pending" | "running" | "done" | "error";

export type AnalyzeStartResponse = {
  status: "started" | "already_running" | "already_complete";
  loan_id: string;
  registered_dimensions: DimensionName[];
};

export type DimensionStatusRow = {
  dimension: DimensionName;
  status: DimensionStatus;
  score: number | null;
  confidence: number | null;
  narrative: string | null;
  error_message: string | null;
  updated_at: string | null;
};

export type DocumentStatusRow = {
  id: string;
  doc_type: string;
  analysis_status: "pending" | "done" | "error";
  extractor_schema_version: string | null;
};

export type AnalyzeStatusResponse = {
  loan_id: string;
  loan_status: LoanStatus;
  synthesis_status: SynthesisStatus;
  dimensions: DimensionStatusRow[];
  documents: DocumentStatusRow[];
  timing: {
    submitted_at: string | null;
    started_at: string | null;
    completed_at: string | null;
    submission_to_decision_s: number | null;
    pipeline_duration_s: number | null;
  };
  analyst_jobs: Record<string, unknown>;
};

export type RiskAppetite = "conservative" | "moderate" | "aggressive";
export type MarketStatus = "low_risk" | "medium_risk" | "high_risk";

export type RiskSnapshot = {
  id: string;
  captured_at: string;
  market_status: MarketStatus;
  market_notes: string | null;
  cashflow_score: number | null;
  risk_appetite: RiskAppetite;
  raw_data: Record<string, unknown>;
  policy_id: string | null;
};

export type CurrentRiskResponse = { snapshot: RiskSnapshot | null };

export type FixturesResponse = {
  loan_id: string;
  uploaded: Array<{ doc_type: string; storage_path: string; document_id: string }>;
};

// ---------- Calls -----------------------------------------------------------

export const api = {
  health: () => request<HealthResponse>("/health"),

  classifyDocument: (storage_path: string) =>
    request<ClassifyResponse>("/documents/classify", {
      method: "POST",
      body: JSON.stringify({ storage_path }),
    }),

  startAnalysis: (loan_id: string) =>
    request<AnalyzeStartResponse>("/analyze/start", {
      method: "POST",
      body: JSON.stringify({ loan_id }),
    }),

  getAnalysisStatus: (loan_id: string) =>
    request<AnalyzeStatusResponse>(`/analyze/status/${loan_id}`),

  getAnalysisTrace: (loan_id: string) =>
    request<{ traces: unknown[]; documents: unknown[] }>(`/analyze/trace/${loan_id}`),

  startAnalyst: (loan_id: string) =>
    request<{ status: string; job_id?: string }>(`/analyze/analyst/start/${loan_id}`, {
      method: "POST",
    }),

  getAnalystStatus: (loan_id: string) =>
    request<Record<string, unknown>>(`/analyze/analyst/status/${loan_id}`),

  getAnalystReport: (loan_id: string) =>
    request<Record<string, unknown>>(`/analyze/analyst/report/${loan_id}`),

  currentRisk: () => request<CurrentRiskResponse>("/risk/current"),

  takeRiskSnapshot: () =>
    request<{ status: "ok"; snapshot: RiskSnapshot }>("/risk/snapshot", {
      method: "POST",
    }),

  /**
   * Install (or re-install) the repayment schedule + Stream subscription for
   * an approved loan. Idempotent on the installments side (skips if any exist).
   * Stream subscription chain retries fresh each call.
   *
   * Use from the admin UI:
   *  - Right after flipping status=approved, to ensure installments + Stream
   *    are provisioned even when the deciding path didn't auto-call it.
   *  - Standalone retry button for legacy approved loans that got stuck.
   */
  installSchedule: (loan_id: string) =>
    request<{
      loan_id: string;
      installments_count: number;
      stream: Record<string, unknown>;
    }>(`/loans/${loan_id}/install-schedule`, { method: "POST" }),

  generateFixtures: (loan_id: string, include?: string[]) =>
    request<FixturesResponse>("/dev/generate-fixtures", {
      method: "POST",
      body: JSON.stringify({ loan_id, include }),
    }),
};

export { ApiError };

import { createClient } from "@supabase/supabase-js";
import { env } from "./env";

export const supabase = createClient(env.SUPABASE_URL, env.SUPABASE_ANON_KEY, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
  realtime: {
    params: { eventsPerSecond: 5 },
  },
});

// ===== Row types — kept in sync with leaseflow/migrations/ ==================
// Don't add service-role-only columns here; the anon key is what ships.

export type UserRole = "merchant" | "admin";

export type Profile = {
  id: string;
  role: UserRole;
  display_name: string | null;
  created_at: string;
};

export type Merchant = {
  id: string;
  user_id: string;
  business_name: string;
  cr_number: string | null;
  google_maps_url: string | null;
  phone: string | null;
  // Populated by the backend on loan approval (migration 0008).
  stream_consumer_id: string | null;
  // Populated by the Google reviews agent (migration 0009).
  google_place_id: string | null;
  google_place_url: string | null;
  google_place_title: string | null;
  google_place_address: string | null;
  google_place_resolved_at: string | null;
  created_at: string;
  updated_at: string;
};

export type LoanStatus =
  | "pending_analysis"
  | "analyzing"
  | "manual_review"
  | "approved"
  | "denied";

export type SynthesisStatus = "pending" | "running" | "done" | "error";

export type RepaymentFrequency = "daily" | "weekly" | "biweekly" | "monthly";

export type Loan = {
  id: string;
  merchant_id: string;
  amount_requested: number;
  item_description: string;
  invoice_url: string | null;
  profit_rate: number;
  repayment_months: number;
  repayment_frequency: RepaymentFrequency;
  status: LoanStatus;
  synthesis_status: SynthesisStatus;
  registered_dimensions: string[] | null;
  decision_payload: Record<string, unknown> | null;
  approved_amount: number | null;
  monthly_payment: number | null;
  amount_paid: number;
  // Populated by the backend on loan approval (migration 0008).
  stream_product_id: string | null;
  stream_subscription_id: string | null;
  stream_subscription_status: string | null;
  created_at: string;
  updated_at: string;
  analysis_started_at: string | null;
  analysis_completed_at: string | null;
};

export type DocType =
  | "bank_statement"
  | "pos_data"
  | "financial_statement"
  | "invoice";

export type Document = {
  id: string;
  loan_id: string;
  doc_type: DocType;
  storage_path: string;
  analysis_status: "pending" | "done" | "error";
  analysis_report: Record<string, unknown> | null;
  extractor_schema_version: string | null;
  content_hash: string | null;
  created_at: string;
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

export type DimensionResult = {
  id: string;
  loan_id: string;
  dimension: DimensionName;
  status: DimensionStatus;
  score: number | null;
  confidence: number | null;
  dimension_version: string | null;
  narrative: string | null;
  result: Record<string, unknown> | null;
  analyst_job_id: string | null;
  error_message: string | null;
  updated_at: string;
};

export type InstallmentStatus = "pending" | "paid" | "overdue" | "cancelled";

export type Installment = {
  id: string;
  loan_id: string;
  installment_number: number;
  due_date: string;
  amount_sar: number;
  status: InstallmentStatus;
  // Migration 0007 — legacy per-installment link columns (kept for pre-0008 loans).
  stream_payment_link_id: string | null;
  stream_payment_url: string | null;
  stream_link_expires_at: string | null;
  // Migration 0008 — filled by the /webhooks/stream handler when a cycle is paid.
  stream_invoice_id: string | null;
  stream_payment_id: string | null;
  paid_at: string | null;
  paid_amount_sar: number | null;
  payment_method: string | null;
  transaction_ref: string | null;
  created_at: string;
  updated_at: string;
};

export type Segment = {
  id: string;
  name: string;
  label: string | null;
  benchmarks: Record<string, unknown>;
  updated_at: string;
};

export type MarketStatus = "low_risk" | "medium_risk" | "high_risk";
export type RiskAppetite = "conservative" | "moderate" | "aggressive";

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

// ===== Storage helpers ======================================================
// Bucket: loan-documents (private). Path convention enforced by RLS:
//   {merchant_id}/{loan_id}/{doc_type}/{uuid}.{ext}
// First segment MUST equal one of your merchant IDs or uploads 403.

export function buildDocPath(
  merchantId: string,
  loanId: string,
  docType: DocType,
  file: File,
): string {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "bin";
  const uuid = crypto.randomUUID();
  return `${merchantId}/${loanId}/${docType}/${uuid}.${ext}`;
}

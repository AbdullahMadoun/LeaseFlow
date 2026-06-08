import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { AdminShell } from "../../components/AdminShell";
import { RiyalSymbol } from "../../components/RiyalSymbol";
import { supabase } from "../../lib/supabase";
import { api, ApiError } from "../../lib/api";
import {
  Card,
  KV,
  Chip,
  ScoreBar,
  Sar,
  RawJson,
  Metric,
  FeatureGrid,
  formatValue,
  formatPct,
} from "../../components/DataViews";

type Loan = {
  id: string;
  merchant_id: string;
  amount_requested: number;
  approved_amount: number | null;
  amount_paid: number | null;
  item_description: string;
  repayment_months: number;
  repayment_frequency: string;
  status: "pending_analysis" | "analyzing" | "approved" | "denied" | "manual_review";
  synthesis_status: string | null;
  profit_rate: number | null;
  decision_payload: DecisionPayload | null;
  created_at: string;
};

type DecisionPayload = {
  schema_version?: string;
  generated_at?: string;
  final_decision?: {
    status?: "approved" | "denied" | "manual_review";
    approved_amount?: number;
    override_applied?: string;
  };
  deterministic_proposal?: {
    decision?: "approve" | "deny" | "review";
    overall_score?: number;
    risk_level?: string;
    rules_fired?: string[];
    amount_bounds?: { min: number; max: number };
    per_dim?: Record<string, number>;
  };
  llm_response?: {
    decision?: string;
    reasoning?: string;
    approved_amount?: number;
    confidence?: number;
    risk_flags?: string[];
    risk_level?: string;
    dimension_scores?: Record<string, number | null>;
    recommended_amount?: number;
  } | null;
  dimension_scores?: Record<string, number>;
  hard_floors_check?: {
    passed?: boolean;
    violations?: string[];
  };
  registered_dimensions?: string[];
  risk_snapshot_id?: string | null;
  synthesis_version?: string;
};

type Merchant = {
  id: string;
  business_name: string;
  cr_number: string | null;
  phone: string | null;
};

type Dim = {
  id: string;
  dimension: "pos" | "financial_docs" | "simah" | "sentiment" | "industry";
  status: "pending" | "running" | "done" | "error";
  score: number | null;
  confidence: number | null;
  narrative: string | null;
  error_message: string | null;
  // result is free-form JSON per DimensionOutput; we read features.reviews
  // from the sentiment dim for the Customer Reviews panel.
  result?: Record<string, unknown> | null;
};

type GoogleReview = {
  author?: string | null;
  rating?: number | string | null;
  text?: string | null;
  date?: string | null;
  relative_date?: string | null;
  likes?: number | null;
  is_local_guide?: boolean | null;
  review_url?: string | null;
};

type DocumentRow = {
  id: string;
  doc_type: "bank_statement" | "financial_statement" | "pos_data" | "invoice";
  analysis_status: "pending" | "processing" | "done" | "error";
  storage_path: string;
  analysis_report: Record<string, unknown> | null;
  extractor_schema_version: string | null;
};

type Trace = {
  id: string;
  stage: string;
  dimension: string | null;
  kind: string;
  model?: string | null;
  duration_ms: number | null;
  created_at: string;
  parsed?: unknown;
  prompt?: { system?: string; user?: string };
  response_raw?: unknown;
  error?: string | null;
};

type Tab = "overview" | "documents" | "decision" | "timeline";

export function AdminLoanDetail() {
  const { id } = useParams<{ id: string }>();
  const loanId = id!;
  const [loan, setLoan] = useState<Loan | null>(null);
  const [merchant, setMerchant] = useState<Merchant | null>(null);
  const [dims, setDims] = useState<Dim[]>([]);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [installmentCount, setInstallmentCount] = useState<number>(0);
  const [traces, setTraces] = useState<Trace[]>([]);
  const [tab, setTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [installingSchedule, setInstallingSchedule] = useState(false);

  const refreshInstallmentCount = async () => {
    const { count } = await supabase
      .from("installments")
      .select("id", { count: "exact", head: true })
      .eq("loan_id", loanId);
    setInstallmentCount(count ?? 0);
  };

  const handleInstallSchedule = async () => {
    setInstallingSchedule(true);
    try {
      const res = await api.installSchedule(loanId);
      await refreshInstallmentCount();
      const streamErr = (res.stream as { error?: string } | null)?.error;
      if (streamErr) {
        toast.warning(
          `${res.installments_count} installments created. Stream subscription failed (${streamErr.slice(0, 80)}) — merchant can still see the ledger.`,
        );
      } else {
        toast.success(`Schedule installed: ${res.installments_count} installments.`);
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : e instanceof Error ? e.message : "install failed";
      toast.error(msg);
    } finally {
      setInstallingSchedule(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { data: loanData } = await supabase.from("loans").select("*").eq("id", loanId).maybeSingle();
      const l = (loanData as Loan | null) ?? null;
      if (cancelled) return;
      setLoan(l);

      if (l) {
        const [{ data: m }, { data: d }, { data: docs }, { count: instCount }] = await Promise.all([
          supabase.from("merchants").select("*").eq("id", l.merchant_id).maybeSingle(),
          supabase.from("dimension_results").select("*").eq("loan_id", loanId),
          supabase.from("documents").select("*").eq("loan_id", loanId),
          supabase.from("installments").select("id", { count: "exact", head: true }).eq("loan_id", loanId),
        ]);
        if (cancelled) return;
        setMerchant((m as Merchant | null) ?? null);
        setDims((d as Dim[] | null) ?? []);
        setDocuments((docs as DocumentRow[] | null) ?? []);
        setInstallmentCount(instCount ?? 0);
      }
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [loanId]);

  // Live-update when the underlying loan changes (pipeline finishes, another
  // admin approves, override fires) so the UI never stales out.
  useEffect(() => {
    const loanCh = supabase
      .channel(`admin-loan:${loanId}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "loans", filter: `id=eq.${loanId}` },
        (payload) => setLoan(payload.new as Loan),
      )
      .subscribe();
    const dimCh = supabase
      .channel(`admin-dims:${loanId}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "dimension_results", filter: `loan_id=eq.${loanId}` },
        (payload) => {
          const row = payload.new as Dim;
          setDims((cur) => {
            const idx = cur.findIndex((x) => x.id === row.id);
            if (idx === -1) return [...cur, row];
            const copy = [...cur];
            copy[idx] = row;
            return copy;
          });
        },
      )
      .subscribe();
    return () => {
      supabase.removeChannel(loanCh);
      supabase.removeChannel(dimCh);
    };
  }, [loanId]);

  useEffect(() => {
    if (tab !== "timeline" || traces.length > 0) return;
    (async () => {
      try {
        const r = (await api.getAnalysisTrace(loanId)) as unknown as { traces?: Trace[] };
        setTraces(r.traces ?? []);
      } catch {
        setTraces([]);
      }
    })();
  }, [tab, loanId, traces.length]);

  if (loading) {
    return (
      <AdminShell activeTab="pipeline">
        <div className="font-mono text-xs uppercase tracking-widest text-on-surface-variant">
          Loading&hellip;
        </div>
      </AdminShell>
    );
  }

  if (!loan) {
    return (
      <AdminShell activeTab="pipeline">
        <div className="bg-white border-[3px] border-black offset-shadow p-8">
          <h2 className="text-2xl font-black uppercase mb-3">Loan not found</h2>
          <Link to="/admin" className="font-mono text-xs font-bold uppercase underline">
            Back to pipeline →
          </Link>
        </div>
      </AdminShell>
    );
  }

  return (
    <AdminShell activeTab="pipeline">
      <div className="mb-6 font-mono text-xs">
        <Link to="/admin" className="uppercase tracking-widest text-on-surface-variant hover:text-black">
          ← Pipeline
        </Link>
      </div>

      <LoanHeader loan={loan} merchant={merchant} />

      <div className="mt-8 mb-6 flex gap-0 border-[3px] border-black bg-white offset-shadow">
        {(["overview", "documents", "decision", "timeline"] as Tab[]).map((t, i, arr) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-4 font-mono text-xs font-black uppercase tracking-widest transition-colors ${
              i < arr.length - 1 ? "border-r-[3px] border-black" : ""
            } ${tab === t ? "bg-primary-container text-black" : "hover:bg-surface-container-high"}`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <Overview
          loan={loan}
          dims={dims}
          installmentCount={installmentCount}
          installingSchedule={installingSchedule}
          onInstallSchedule={handleInstallSchedule}
        />
      )}
      {tab === "documents" && <DocumentsTab documents={documents} />}
      {tab === "decision" && <DecisionTab loan={loan} />}
      {tab === "timeline" && <TimelineTab traces={traces} />}
    </AdminShell>
  );
}

function LoanHeader({ loan, merchant }: { loan: Loan; merchant: Merchant | null }) {
  return (
    <div className="bg-white border-[3px] border-black offset-shadow-md p-6">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
        <div className="md:col-span-5">
          <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
            Merchant
          </div>
          <div className="mt-1 text-3xl font-black tracking-tight">{merchant?.business_name ?? "Unknown"}</div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
            CR {merchant?.cr_number ?? "—"} · {merchant?.phone ?? "—"}
          </div>
          <div className="mt-3 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
            Lease #{loan.id.slice(0, 8)} · {loan.item_description}
          </div>
        </div>
        <div className="md:col-span-3">
          <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
            Requested
          </div>
          <div className="mt-1 font-display text-4xl font-black flex items-baseline gap-2">
            <RiyalSymbol className="h-[0.75em] w-[0.68em] translate-y-[0.05em]" />
            <span>{loan.amount_requested.toLocaleString("en-US")}</span>
          </div>
          {loan.approved_amount != null && (
            <div className="mt-2 font-mono text-[10px] uppercase tracking-widest text-success">
              Approved: {loan.approved_amount.toLocaleString("en-US")}
            </div>
          )}
        </div>
        <div className="md:col-span-2">
          <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
            Term
          </div>
          <div className="mt-1 font-display text-2xl font-black">{loan.repayment_months} mo</div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
            {loan.repayment_frequency}
          </div>
        </div>
        <div className="md:col-span-2 text-right">
          <StatusChipBig status={loan.status} />
        </div>
      </div>
    </div>
  );
}

function StatusChipBig({ status }: { status: Loan["status"] }) {
  const map: Record<Loan["status"], string> = {
    pending_analysis: "bg-white",
    analyzing: "bg-primary-container animate-pulse",
    manual_review: "bg-warning text-white",
    approved: "bg-success text-white",
    denied: "bg-error text-white",
  };
  return (
    <span className={`inline-block font-mono text-xs font-black uppercase tracking-widest px-4 py-2 border-[3px] border-black ${map[status]}`}>
      {status.replace("_", " ")}
    </span>
  );
}

/* ─── Tab: Overview ───────────────────────────────────────────────────── */

function Overview({
  loan, dims, installmentCount, installingSchedule, onInstallSchedule,
}: {
  loan: Loan;
  dims: Dim[];
  installmentCount: number;
  installingSchedule: boolean;
  onInstallSchedule: () => void;
}) {
  const dp = loan.decision_payload;
  const needsSchedule = loan.status === "approved" && installmentCount === 0;
  return (
    <div className="space-y-6">
      {loan.status === "manual_review" && (
        <ManualOverridePanel loan={loan} onAfterApprove={onInstallSchedule} />
      )}
      {needsSchedule && (
        <div className="bg-warning text-white border-[3px] border-black offset-shadow-md p-6">
          <div className="font-mono text-xs font-black uppercase tracking-widest mb-2">
            ⚠ Schedule missing
          </div>
          <p className="mb-4 text-sm opacity-90">
            This loan is approved but has no repayment schedule. Install now to create
            installments and the Stream subscription.
          </p>
          <button
            onClick={onInstallSchedule}
            disabled={installingSchedule}
            className="bg-black text-white border-[3px] border-black px-5 py-3 font-mono text-xs font-black uppercase tracking-widest offset-shadow hover-lift disabled:opacity-40"
          >
            {installingSchedule ? "Installing…" : "Install schedule"}
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-0 border-[3px] border-black bg-white offset-shadow">
        <KpiCell
          label="Overall score"
          value={dp?.deterministic_proposal?.overall_score != null
            ? dp.deterministic_proposal.overall_score.toString()
            : "—"}
          border="border-r-[3px]"
        />
        <KpiCell label="Proposed" value={dp?.deterministic_proposal?.decision ?? "—"} border="border-r-[3px]" />
        <KpiCell label="LLM decision" value={dp?.llm_response?.decision ?? "—"} border="border-r-[3px]" />
        <KpiCell label="Override" value={dp?.final_decision?.override_applied ?? "—"} />
      </div>

      <div className="bg-white border-[3px] border-black offset-shadow p-6">
        <div className="font-mono text-[10px] font-bold uppercase tracking-widest mb-4">
          Dimension scores
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {(["pos", "financial_docs", "simah", "sentiment", "industry"] as const).map((key) => {
            const d = dims.find((x) => x.dimension === key);
            return (
              <div key={key} className="border-[3px] border-black p-4">
                <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
                  {key.replace("_", " ")}
                </div>
                <div className="mt-2 font-display text-3xl font-black">
                  {d?.score != null ? d.score : "—"}
                </div>
                <div className="mt-1 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
                  {d?.status ?? "pending"}
                  {d?.confidence != null && ` · ${Math.round(d.confidence * 100)}%`}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <CustomerReviewsPanel dims={dims} />

      {dp?.deterministic_proposal?.rules_fired && dp.deterministic_proposal.rules_fired.length > 0 && (
        <div className="bg-white border-[3px] border-black offset-shadow p-6">
          <div className="font-mono text-[10px] font-bold uppercase tracking-widest mb-3">
            Rules fired ({dp.deterministic_proposal.rules_fired.length})
          </div>
          <div className="flex flex-wrap gap-2">
            {dp.deterministic_proposal.rules_fired.map((r) => (
              <span key={r} className="font-mono text-[10px] font-bold uppercase tracking-widest px-2 py-1 border-[3px] border-black">
                {r}
              </span>
            ))}
          </div>
        </div>
      )}

      {dp?.hard_floors_check?.violations && dp.hard_floors_check.violations.length > 0 && (
        <div className="bg-error text-white border-[3px] border-black offset-shadow p-6">
          <div className="font-mono text-[10px] font-bold uppercase tracking-widest mb-3">
            Hard floors violated ({dp.hard_floors_check.violations.length})
          </div>
          <div className="flex flex-wrap gap-2">
            {dp.hard_floors_check.violations.map((h) => (
              <span key={h} className="font-mono text-[10px] font-bold uppercase tracking-widest px-2 py-1 border-[3px] border-white">
                {h}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KpiCell({ label, value, border = "" }: { label: string; value: string | number; border?: string }) {
  return (
    <div className={`${border} border-black p-5`}>
      <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
        {label}
      </div>
      <div className="mt-2 font-display text-3xl font-black truncate">{value}</div>
    </div>
  );
}

function ManualOverridePanel({
  loan, onAfterApprove,
}: {
  loan: Loan;
  onAfterApprove: () => void;
}) {
  const bounds = loan.decision_payload?.deterministic_proposal?.amount_bounds;
  const [amount, setAmount] = useState<number>(bounds?.max ?? loan.amount_requested);
  const [working, setWorking] = useState(false);

  const approve = async () => {
    if (bounds && (amount < bounds.min || amount > bounds.max)) {
      toast.error(`Amount must be between ${bounds.min.toLocaleString()} and ${bounds.max.toLocaleString()}`);
      return;
    }
    setWorking(true);
    const { error } = await supabase
      .from("loans")
      .update({ status: "approved", approved_amount: amount })
      .eq("id", loan.id)
      .select()
      .single();
    setWorking(false);
    if (error) return toast.error(error.message);
    toast.success(`Approved at SAR ${amount.toLocaleString()}. Installing schedule…`);
    // Synchronously trigger schedule install — the expert.synthesize pipeline
    // isn't re-run on admin UPDATE, so we do it explicitly.
    onAfterApprove();
  };

  const deny = async () => {
    setWorking(true);
    const { data, error } = await supabase
      .from("loans")
      .update({ status: "denied" })
      .eq("id", loan.id)
      .select()
      .single();
    setWorking(false);
    if (error) return toast.error(error.message);
    toast.success(data ? "Denied — status updated." : "Denied.");
  };

  return (
    <div className="bg-warning text-white border-[3px] border-black offset-shadow-md p-6">
      <div className="font-mono text-xs font-black uppercase tracking-widest mb-3">
        Manual override
      </div>
      <p className="mb-4 text-sm opacity-90">
        This loan needs your call. Bounds from the deterministic proposal:{" "}
        <b>
          SAR {bounds?.min?.toLocaleString() ?? "—"} – {bounds?.max?.toLocaleString() ?? "—"}
        </b>
        .
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="block font-mono text-[10px] font-black uppercase tracking-widest mb-1">
            Approve at (SAR)
          </label>
          <input
            type="number"
            value={amount}
            min={bounds?.min}
            max={bounds?.max}
            onChange={(e) => setAmount(Number(e.target.value))}
            className="border-[3px] border-black bg-white text-black p-2 font-mono text-lg font-black w-48"
          />
        </div>
        <button
          onClick={approve}
          disabled={working}
          className="bg-success text-white border-[3px] border-black px-5 py-3 font-mono text-xs font-black uppercase tracking-widest offset-shadow hover-lift disabled:opacity-40"
        >
          Approve
        </button>
        <button
          onClick={deny}
          disabled={working}
          className="bg-error text-white border-[3px] border-black px-5 py-3 font-mono text-xs font-black uppercase tracking-widest offset-shadow hover-lift disabled:opacity-40"
        >
          Deny
        </button>
      </div>
      <div className="mt-4 font-mono text-[10px] uppercase tracking-widest opacity-70">
        Note: admin approve does not auto-install the repayment schedule yet (backend gap).
      </div>
    </div>
  );
}

/* ─── Tab: Documents ──────────────────────────────────────────────────── */

function DocumentsTab({ documents }: { documents: DocumentRow[] }) {
  if (documents.length === 0) {
    return (
      <div className="bg-white border-[3px] border-black offset-shadow p-8 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
        No documents uploaded.
      </div>
    );
  }
  return (
    <div className="space-y-4">
      {documents.map((d) => (
        <DocumentCard key={d.id} doc={d} />
      ))}
    </div>
  );
}

function DocumentCard({ doc }: { doc: DocumentRow }) {
  const report = (doc.analysis_report ?? null) as Record<string, unknown> | null;
  const filename = doc.storage_path.split("/").pop() ?? doc.storage_path;
  const statusTone =
    doc.analysis_status === "done" ? "success"
    : doc.analysis_status === "error" ? "error"
    : "info";

  return (
    <div className="bg-white border-[3px] border-black offset-shadow p-6">
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <div className="font-display text-2xl font-black uppercase tracking-tight">
            {doc.doc_type.replace(/_/g, " ")}
          </div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
            {filename}
            {doc.extractor_schema_version && ` · v${doc.extractor_schema_version}`}
          </div>
        </div>
        <Chip tone={statusTone}>{doc.analysis_status}</Chip>
      </div>

      {!report && (
        <div className="font-mono text-xs uppercase tracking-widest text-on-surface-variant">
          No analysis yet.
        </div>
      )}

      {report && (report.error as string | undefined) && (
        <div className="bg-error/10 border-[3px] border-error p-3 font-mono text-xs mb-4">
          {String(report.error).slice(0, 300)}
        </div>
      )}

      {report && <DocumentReport docType={doc.doc_type} report={report} />}

      {report && <div className="mt-4"><RawJson data={report} label="Raw analysis report" /></div>}
    </div>
  );
}

function DocumentReport({
  docType,
  report,
}: {
  docType: DocumentRow["doc_type"];
  report: Record<string, unknown>;
}) {
  const meta = (report.meta ?? {}) as Record<string, unknown>;
  const sourcePages = (report.source_pages as number[] | undefined) ?? (meta.source_pages as number[] | undefined);
  const confidence = (meta.confidence as number | undefined) ?? (report.confidence as number | undefined);

  return (
    <div className="space-y-4">
      {(sourcePages || confidence != null) && (
        <div className="flex flex-wrap gap-2">
          {confidence != null && (
            <Chip tone={confidence >= 0.75 ? "success" : confidence >= 0.55 ? "info" : "warning"}>
              {Math.round(confidence * 100)}% confident
            </Chip>
          )}
          {sourcePages && sourcePages.length > 0 && (
            <Chip>pages {sourcePages.join(", ")}</Chip>
          )}
        </div>
      )}

      {docType === "bank_statement" && <BankStatementReport report={report} />}
      {docType === "financial_statement" && <FinancialStatementReport report={report} />}
      {docType === "pos_data" && <PosDataReport report={report} />}
      {docType === "invoice" && <InvoiceReport report={report} />}
    </div>
  );
}

function BankStatementReport({ report }: { report: Record<string, unknown> }) {
  const opening = report.opening_balance_sar as number | undefined;
  const closing = report.closing_balance_sar as number | undefined;
  const inflows = report.total_inflows_sar as number | undefined;
  const outflows = report.total_outflows_sar as number | undefined;
  const net = report.net_flow_sar as number | undefined;
  const monthsCovered = report.months_covered as number | undefined;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <Metric label="Opening" value={<Sar amount={opening} size="lg" />} />
      <Metric label="Closing" value={<Sar amount={closing} size="lg" />} />
      <Metric label="Inflows" value={<Sar amount={inflows} size="lg" />} sub={monthsCovered ? `over ${monthsCovered} mo` : undefined} />
      <Metric label="Outflows" value={<Sar amount={outflows} size="lg" />} sub={net != null ? `net ${net >= 0 ? "+" : ""}${net.toLocaleString()}` : undefined} />
    </div>
  );
}

function FinancialStatementReport({ report }: { report: Record<string, unknown> }) {
  const income = (report.income_statement ?? {}) as Record<string, unknown>;
  const balance = (report.balance_sheet ?? {}) as Record<string, unknown>;
  const ratios = (report.ratios ?? {}) as Record<string, unknown>;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric label="Revenue" value={<Sar amount={income.revenue_sar as number | undefined} size="lg" />} />
        <Metric label="COGS" value={<Sar amount={income.cogs_sar as number | undefined} size="lg" />} />
        <Metric label="OpEx" value={<Sar amount={income.opex_sar as number | undefined} size="lg" />} />
        <Metric label="Net profit" value={<Sar amount={income.net_profit_sar as number | undefined} size="lg" />} />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric label="Total assets" value={<Sar amount={balance.total_assets_sar as number | undefined} size="lg" />} />
        <Metric label="Equity" value={<Sar amount={balance.equity_sar as number | undefined} size="lg" />} />
        <Metric label="Liabilities" value={<Sar amount={balance.total_liabilities_sar as number | undefined} size="lg" />} />
        <Metric label="Current assets" value={<Sar amount={balance.current_assets_sar as number | undefined} size="lg" />} />
      </div>
      {Object.keys(ratios).length > 0 && (
        <div>
          <div className="font-mono text-[10px] font-black uppercase tracking-widest mb-2">
            Ratios
          </div>
          <FeatureGrid
            features={ratios}
            formatters={{
              net_margin: formatPct,
              gross_margin: formatPct,
              current_ratio: formatValue,
              debt_to_equity: formatValue,
            }}
          />
        </div>
      )}
    </div>
  );
}

function PosDataReport({ report }: { report: Record<string, unknown> }) {
  const summary = (report.summary ?? report) as Record<string, unknown>;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric label="Revenue" value={<Sar amount={summary.revenue_sar as number | undefined} size="lg" />} />
        <Metric label="Avg ticket" value={<Sar amount={summary.avg_ticket_sar as number | undefined} size="lg" />} />
        <Metric
          label="Transactions"
          value={<span className="font-display text-2xl">{formatValue(summary.transactions_count)}</span>}
        />
        <Metric
          label="Days covered"
          value={<span className="font-display text-2xl">{formatValue(summary.days_covered)}</span>}
        />
      </div>
      {summary.top_skus as unknown as unknown[] | undefined && Array.isArray(summary.top_skus) && (
        <div>
          <div className="font-mono text-[10px] font-black uppercase tracking-widest mb-2">Top items</div>
          <div className="flex flex-wrap gap-2">
            {(summary.top_skus as Record<string, unknown>[]).slice(0, 8).map((sku, i) => (
              <Chip key={i}>{String(sku.name ?? sku.sku ?? "item")}: {formatValue(sku.revenue_sar ?? sku.count)}</Chip>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function InvoiceReport({ report }: { report: Record<string, unknown> }) {
  const vendor = report.vendor_name as string | undefined;
  const item = (report.item_description as string | undefined) ?? (report.description as string | undefined);
  const amount = (report.total_sar as number | undefined) ?? (report.amount_sar as number | undefined);
  const date = report.invoice_date as string | undefined;
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Metric label="Vendor" value={<span className="text-lg">{vendor ?? "—"}</span>} />
        <Metric label="Amount" value={<Sar amount={amount} size="lg" />} sub={date} />
      </div>
      {item && (
        <div className="border-[3px] border-black bg-white p-4">
          <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">
            Item
          </div>
          <div className="text-base">{item}</div>
        </div>
      )}
    </div>
  );
}

/* ─── Tab: Decision ───────────────────────────────────────────────────── */

function DecisionTab({ loan }: { loan: Loan }) {
  const dp = loan.decision_payload;
  if (!dp) {
    return (
      <div className="bg-white border-[3px] border-black offset-shadow p-8 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
        Decision payload not yet available.
      </div>
    );
  }

  const final = dp.final_decision ?? {};
  const proposal = dp.deterministic_proposal ?? {};
  const llm = dp.llm_response ?? null;
  const floors = dp.hard_floors_check ?? {};
  const scores = (dp.dimension_scores ?? {}) as Record<string, number | null>;

  const finalTone =
    final.status === "approved" ? "success"
    : final.status === "denied" ? "error"
    : final.status === "manual_review" ? "warning"
    : "secondary";

  const overrideCopy: Record<string, string> = {
    agreement: "deterministic + LLM agreed",
    llm_downgrade: "LLM was stricter than rules",
    llm_upgrade_blocked: "LLM tried to upgrade; rules blocked",
    llm_primary: "LLM decided unilaterally",
    llm_unavailable_deterministic_only: "LLM unavailable; rules only",
    hard_floor: "failed a hard floor",
  };

  return (
    <div className="space-y-6">
      {/* Final decision headline */}
      <Card label="Final decision" tone={finalTone}>
        <div className="flex flex-wrap items-baseline gap-6 justify-between">
          <div>
            <div className="font-display text-5xl font-black uppercase tracking-tighter">
              {final.status ?? "—"}
            </div>
            {final.override_applied && (
              <div className="mt-2 font-mono text-[10px] uppercase tracking-widest opacity-80">
                {final.override_applied} · {overrideCopy[final.override_applied] ?? "override"}
              </div>
            )}
          </div>
          {final.approved_amount != null && (
            <div className="text-right">
              <div className="font-mono text-[10px] uppercase tracking-widest opacity-80">
                Approved
              </div>
              <Sar amount={final.approved_amount} size="xl" />
            </div>
          )}
        </div>
      </Card>

      {/* Side-by-side proposal vs LLM */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card label="Deterministic proposal · rules engine">
          <KV k="Decision" v={<Chip tone={proposal.decision === "approve" ? "success" : proposal.decision === "deny" ? "error" : "warning"}>{proposal.decision ?? "—"}</Chip>} />
          <KV k="Overall score" v={<span className="font-display text-xl font-black">{formatValue(proposal.overall_score)}</span>} />
          <KV k="Risk level" v={proposal.risk_level ? <Chip tone={proposal.risk_level === "low" ? "success" : proposal.risk_level === "high" ? "error" : "warning"}>{proposal.risk_level}</Chip> : "—"} />
          <KV
            k="Amount bounds"
            v={
              proposal.amount_bounds ? (
                <span>
                  <Sar amount={proposal.amount_bounds.min} size="sm" /> — <Sar amount={proposal.amount_bounds.max} size="sm" />
                </span>
              ) : "—"
            }
          />
          {proposal.rules_fired && proposal.rules_fired.length > 0 && (
            <div className="mt-3 pt-3 border-t-[3px] border-dashed border-black">
              <div className="font-mono text-[10px] font-black uppercase tracking-widest mb-2">
                Rules fired ({proposal.rules_fired.length})
              </div>
              <div className="flex flex-wrap gap-2">
                {proposal.rules_fired.map((r) => <Chip key={r}>{r.replace(/_/g, " ")}</Chip>)}
              </div>
            </div>
          )}
        </Card>

        <Card label="LLM synthesis · MiniMax" tone={llm ? "white" : "secondary"}>
          {!llm ? (
            <div className="font-mono text-xs uppercase tracking-widest opacity-80">
              LLM unavailable — deterministic-only decision
            </div>
          ) : (
            <>
              <KV k="Decision" v={<Chip tone={llm.decision === "approve" ? "success" : llm.decision === "deny" ? "error" : "warning"}>{llm.decision ?? "—"}</Chip>} />
              {llm.confidence != null && (
                <KV k="Confidence" v={<span className="font-mono">{Math.round(llm.confidence * 100)}%</span>} />
              )}
              {llm.approved_amount != null && <KV k="Recommended" v={<Sar amount={llm.approved_amount} size="sm" />} />}
              {llm.reasoning && (
                <div className="mt-3 pt-3 border-t-[3px] border-dashed border-black">
                  <div className="font-mono text-[10px] font-black uppercase tracking-widest mb-2">
                    Reasoning
                  </div>
                  <p className="text-sm leading-snug">{llm.reasoning}</p>
                </div>
              )}
              {(llm as unknown as { risk_flags?: string[] }).risk_flags && (
                <div className="mt-3 pt-3 border-t-[3px] border-dashed border-black">
                  <div className="font-mono text-[10px] font-black uppercase tracking-widest mb-2">
                    Risk flags
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(llm as unknown as { risk_flags: string[] }).risk_flags.map((f) => (
                      <Chip key={f} tone="warning">{f.replace(/_/g, " ")}</Chip>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </Card>
      </div>

      {/* Dimension scores row */}
      {Object.keys(scores).length > 0 && (
        <Card label="Dimension scores">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {(["pos", "financial_docs", "simah", "sentiment", "industry"] as const).map((key) => (
              <ScoreBar
                key={key}
                label={key.replace("_", " ")}
                score={scores[key] ?? scores[key === "financial_docs" ? "financial" : key] ?? null}
              />
            ))}
          </div>
        </Card>
      )}

      {/* Hard floors */}
      <Card label="Hard floors" tone={floors.passed === false ? "error" : "white"}>
        <div className="flex items-center gap-3 flex-wrap">
          <Chip tone={floors.passed ? "success" : "error"}>
            {floors.passed ? "✓ Passed" : "✕ Failed"}
          </Chip>
          {floors.violations && floors.violations.length > 0 && floors.violations.map((v) => (
            <Chip key={v} tone="error">{v.replace(/_/g, " ")}</Chip>
          ))}
        </div>
      </Card>

      {/* Collapsible raw at bottom */}
      <RawJson data={dp} label="Full decision payload (raw)" />
    </div>
  );
}

/* ─── Tab: Timeline ───────────────────────────────────────────────────── */

function TimelineTab({ traces }: { traces: Trace[] }) {
  if (traces.length === 0) {
    return (
      <div className="bg-white border-[3px] border-black offset-shadow p-8 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
        No traces yet — pipeline may still be running.
      </div>
    );
  }

  // Aggregate summary at top
  const totalMs = traces.reduce((s, t) => s + (t.duration_ms ?? 0), 0);
  const byKind = traces.reduce<Record<string, number>>((acc, t) => {
    acc[t.kind] = (acc[t.kind] ?? 0) + 1;
    return acc;
  }, {});
  const withError = traces.filter((t) => t.error).length;

  return (
    <div className="space-y-3">
      <div className="bg-secondary text-white border-[3px] border-black offset-shadow p-4 flex items-center gap-6 flex-wrap">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest opacity-80">Events</div>
          <div className="font-display text-2xl font-black">{traces.length}</div>
        </div>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest opacity-80">Total time</div>
          <div className="font-display text-2xl font-black">{(totalMs / 1000).toFixed(1)}s</div>
        </div>
        {withError > 0 && (
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest opacity-80">Errors</div>
            <div className="font-display text-2xl font-black text-[#FDC800]">{withError}</div>
          </div>
        )}
        <div className="flex gap-2 flex-wrap">
          {Object.entries(byKind).map(([k, n]) => (
            <span key={k} className="font-mono text-[10px] font-black uppercase tracking-widest border-[2px] border-white px-2 py-1">
              {k} · {n}
            </span>
          ))}
        </div>
      </div>

      {traces.map((t) => (
        <TraceRow key={t.id} trace={t} />
      ))}
    </div>
  );
}

// ----------------------------------------------------------------------
// Customer reviews panel — renders sentiment.features.reviews from the
// Google Maps dim as RTL-aware review cards.
// ----------------------------------------------------------------------
function CustomerReviewsPanel({ dims }: { dims: Dim[] }) {
  const sentiment = dims.find((d) => d.dimension === "sentiment");
  const features = (sentiment?.result as { features?: Record<string, unknown> } | null)?.features;
  const reviews = (features as { reviews?: GoogleReview[] } | undefined)?.reviews;
  if (!Array.isArray(reviews) || reviews.length === 0) return null;

  const source = (features as { reviews_source?: { place_title?: string; scraped_rating?: number; scraped_review_count?: number; place_url?: string } } | undefined)?.reviews_source;
  const rating = (features as { google_rating?: number } | undefined)?.google_rating;
  const total = (features as { review_count?: number } | undefined)?.review_count;

  return (
    <div className="bg-white border-[3px] border-black offset-shadow p-6">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="font-mono text-[10px] font-bold uppercase tracking-widest">
          Customer reviews
          {rating != null && <span className="ml-2">· ★ {Number(rating).toFixed(1)}</span>}
          {total != null && <span className="ml-2 text-on-surface-variant">({Number(total).toLocaleString()} total)</span>}
        </div>
        {source?.place_title && (
          <a
            href={source.place_url || "#"}
            target="_blank"
            rel="noreferrer"
            className="font-mono text-[10px] text-on-surface-variant hover:text-black flex items-center gap-1"
          >
            via Google Maps · {source.place_title}
            <span className="material-symbols-outlined text-xs">open_in_new</span>
          </a>
        )}
      </div>
      <div className="space-y-3">
        {reviews.map((r, i) => (
          <ReviewCard key={i} review={r} />
        ))}
      </div>
    </div>
  );
}

function ReviewCard({ review }: { review: GoogleReview }) {
  const stars = Math.max(0, Math.min(5, Math.round(Number(review.rating) || 0)));
  const dateStr = review.date
    ? new Date(review.date).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })
    : review.relative_date || "";
  return (
    <article className="border-[3px] border-black p-4 bg-surface-container-low">
      <div className="flex items-center justify-between mb-2">
        <div className="font-mono text-sm font-bold tracking-widest">
          <span className="text-yellow-600">{"★".repeat(stars)}</span>
          <span className="text-gray-300">{"☆".repeat(5 - stars)}</span>
        </div>
        {dateStr && (
          <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
            {dateStr}
          </div>
        )}
      </div>
      <p
        dir="rtl"
        lang="ar"
        className="text-sm leading-relaxed whitespace-pre-wrap text-right"
        style={{ fontFamily: "system-ui, -apple-system, 'Noto Sans Arabic', sans-serif" }}
      >
        {review.text}
      </p>
      <div className="mt-3 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
        — {review.author || "Anonymous"}
        {review.is_local_guide && <span className="ml-2">· Local Guide</span>}
        {typeof review.likes === "number" && review.likes > 0 && (
          <span className="ml-2">· {review.likes} helpful</span>
        )}
      </div>
    </article>
  );
}

// ----------------------------------------------------------------------
// Timeline trace renderer (from PR #13) — rich expandable rows for each
// ai_traces event on the Timeline tab.
// ----------------------------------------------------------------------
function TraceRow({ trace: t }: { trace: Trace }) {
  const kindTone =
    t.error ? "bg-error text-white"
    : t.kind === "llm_call" ? "bg-secondary text-white"
    : t.kind === "extraction" ? "bg-primary-container text-black"
    : t.kind === "aggregation" ? "bg-success text-white"
    : t.kind === "reconcile" ? "bg-tertiary text-white"
    : "bg-white";

  const parsed = (() => {
    const p = t.parsed;
    if (p == null) return null;
    if (typeof p === "string") { try { return JSON.parse(p) as Record<string, unknown>; } catch { return null; } }
    if (typeof p === "object") return p as Record<string, unknown>;
    return null;
  })();

  const headline = (() => {
    if (!parsed) return null;
    const decision = parsed.decision as string | undefined;
    const score = parsed.score as number | undefined;
    const confidence = parsed.confidence as number | undefined;
    if (decision) {
      return (
        <span className="inline-flex items-center gap-2 ml-3">
          <Chip tone={decision === "approve" ? "success" : decision === "deny" ? "error" : "warning"}>{decision}</Chip>
          {confidence != null && <span className="font-mono text-xs">{Math.round(confidence * 100)}%</span>}
        </span>
      );
    }
    if (score != null) {
      return (
        <span className="inline-flex items-center gap-2 ml-3">
          <span className="font-display text-lg font-black">{score.toFixed(0)}</span>
          {confidence != null && <span className="font-mono text-xs opacity-70">@ {Math.round(confidence * 100)}%</span>}
        </span>
      );
    }
    return null;
  })();

  return (
    <details className="bg-white border-[3px] border-black offset-shadow">
      <summary className="cursor-pointer list-none p-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0 flex-wrap">
          <span
            className={`font-mono text-[10px] font-black uppercase tracking-widest px-2 py-1 border-[3px] border-black shrink-0 ${kindTone}`}
          >
            {t.kind}
          </span>
          <div className="min-w-0">
            <div className="font-bold truncate flex items-center">
              {t.stage.replace(/_/g, " ")}
              {headline}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
              {t.dimension ?? "—"}
              {t.model && ` · ${t.model}`}
              {t.duration_ms != null && ` · ${t.duration_ms}ms`}
              {" · "}
              {new Date(t.created_at).toLocaleTimeString()}
            </div>
          </div>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant shrink-0">
          expand ▸
        </span>
      </summary>

      <div className="border-t-[3px] border-dashed border-black p-4 space-y-4">
        {t.error && (
          <div className="bg-error/10 border-[3px] border-error p-3 font-mono text-xs">
            <div className="font-black uppercase tracking-widest mb-1">Error</div>
            {t.error}
          </div>
        )}

        {parsed && <ParsedView parsed={parsed} />}

        {t.prompt && (
          <details className="bg-surface-container-low border-[3px] border-black">
            <summary className="cursor-pointer list-none p-3 font-mono text-[10px] font-black uppercase tracking-widest">
              ▸ Prompt ({t.model ?? "model"})
            </summary>
            <div className="p-3 border-t-[3px] border-black space-y-3">
              <PromptView prompt={t.prompt} />
            </div>
          </details>
        )}

        <RawJson data={t} label="Raw trace row" />
      </div>
    </details>
  );
}

function ParsedView({ parsed }: { parsed: Record<string, unknown> }) {
  const { reasoning, risk_flags, dimension_scores, ...rest } = parsed as {
    reasoning?: string;
    risk_flags?: string[];
    dimension_scores?: Record<string, number | null>;
  } & Record<string, unknown>;

  const scalarKeys = Object.keys(rest).filter((k) => {
    const v = rest[k];
    return v == null || ["string", "number", "boolean"].includes(typeof v);
  });
  const objectKeys = Object.keys(rest).filter((k) => !scalarKeys.includes(k));

  return (
    <div className="space-y-3">
      {scalarKeys.length > 0 && (
        <FeatureGrid features={Object.fromEntries(scalarKeys.map((k) => [k, rest[k]]))} />
      )}
      {reasoning && (
        <div className="bg-surface-container-low border-[3px] border-black p-3">
          <div className="font-mono text-[10px] font-black uppercase tracking-widest mb-2">
            Reasoning
          </div>
          <p className="text-sm leading-snug">{reasoning}</p>
        </div>
      )}
      {Array.isArray(risk_flags) && risk_flags.length > 0 && (
        <div>
          <div className="font-mono text-[10px] font-black uppercase tracking-widest mb-2">
            Risk flags
          </div>
          <div className="flex flex-wrap gap-2">
            {risk_flags.map((f) => <Chip key={f} tone="warning">{f.replace(/_/g, " ")}</Chip>)}
          </div>
        </div>
      )}
      {dimension_scores && typeof dimension_scores === "object" && (
        <div>
          <div className="font-mono text-[10px] font-black uppercase tracking-widest mb-2">
            Dimension scores
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {Object.entries(dimension_scores as Record<string, number | null>).map(([k, v]) => (
              <div key={k} className="border-[3px] border-black bg-white px-3 py-2">
                <div className="font-mono text-[9px] uppercase tracking-widest text-on-surface-variant">
                  {k.replace(/_/g, " ")}
                </div>
                <div className="font-display text-xl font-black">{v == null ? "—" : v}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      {objectKeys.length > 0 && (
        <div className="space-y-3">
          <div className="font-mono text-[10px] font-black uppercase tracking-widest">
            Nested fields
          </div>
          {objectKeys.map((k) => (
            <NestedObjectCard key={k} label={k} data={rest[k]} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Render an arbitrary JSON value (object / array / primitive) as a structured
 *  mini-card instead of a <pre>{JSON.stringify(...)}</pre> dump.
 *  Depth-1 recursion: scalars flatten into a FeatureGrid, nested objects
 *  become labeled sub-blocks, primitive arrays show as chip rows. */
function NestedObjectCard({ label, data }: { label: string; data: unknown }) {
  return (
    <div className="bg-white border-[3px] border-black p-4">
      <div className="font-mono text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-3">
        {label.replace(/_/g, " ")}
      </div>
      <NestedValue data={data} />
    </div>
  );
}

function NestedValue({ data }: { data: unknown }) {
  if (data == null) {
    return <span className="font-mono text-xs text-on-surface-variant">—</span>;
  }
  if (typeof data !== "object") {
    return <span className="font-mono text-sm font-bold">{formatValue(data)}</span>;
  }
  if (Array.isArray(data)) {
    if (data.length === 0) {
      return <span className="font-mono text-xs text-on-surface-variant italic">empty</span>;
    }
    const allPrimitive = data.every((x) => x == null || typeof x !== "object");
    if (allPrimitive) {
      return (
        <div className="flex flex-wrap gap-2">
          {data.map((x, i) => <Chip key={i}>{formatValue(x)}</Chip>)}
        </div>
      );
    }
    return (
      <div className="space-y-2">
        {data.slice(0, 20).map((row, i) => (
          <div key={i} className="border-[2px] border-black/30 bg-surface-container-low p-3">
            <div className="font-mono text-[9px] uppercase tracking-widest text-on-surface-variant mb-1">
              [{i}]
            </div>
            <NestedValue data={row} />
          </div>
        ))}
        {data.length > 20 && (
          <div className="font-mono text-[10px] text-on-surface-variant">
            · · · {data.length - 20} more items
          </div>
        )}
      </div>
    );
  }

  // object — split into scalars vs nested
  const obj = data as Record<string, unknown>;
  const scalarEntries: [string, unknown][] = [];
  const nestedEntries: [string, unknown][] = [];
  for (const [k, v] of Object.entries(obj)) {
    if (v == null || typeof v !== "object") scalarEntries.push([k, v]);
    else nestedEntries.push([k, v]);
  }

  return (
    <div className="space-y-3">
      {scalarEntries.length > 0 && (
        <FeatureGrid features={Object.fromEntries(scalarEntries)} />
      )}
      {nestedEntries.map(([k, v]) => (
        <div key={k} className="border-l-[3px] border-black pl-3">
          <div className="font-mono text-[9px] font-black uppercase tracking-widest text-on-surface-variant mb-2">
            {k.replace(/_/g, " ")}
          </div>
          <NestedValue data={v} />
        </div>
      ))}
    </div>
  );
}

function PromptView({ prompt }: { prompt: Record<string, unknown> }) {
  const system = prompt.system as string | undefined;
  const user = prompt.user as string | undefined;
  return (
    <>
      {system && (
        <div>
          <div className="font-mono text-[10px] font-black uppercase tracking-widest mb-1">
            System
          </div>
          <pre className="bg-white border-[3px] border-black p-3 font-mono text-[10px] overflow-auto max-h-40 whitespace-pre-wrap">
            {system}
          </pre>
        </div>
      )}
      {user && (
        <div>
          <div className="font-mono text-[10px] font-black uppercase tracking-widest mb-1">
            User
          </div>
          <pre className="bg-white border-[3px] border-black p-3 font-mono text-[10px] overflow-auto max-h-64 whitespace-pre-wrap">
            {user}
          </pre>
        </div>
      )}
      {!system && !user && (
        <pre className="bg-white border-[3px] border-black p-3 font-mono text-[10px] overflow-auto max-h-64 whitespace-pre-wrap break-all">
          {JSON.stringify(prompt, null, 2)}
        </pre>
      )}
    </>
  );
}

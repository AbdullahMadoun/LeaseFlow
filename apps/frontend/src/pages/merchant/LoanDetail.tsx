import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { MerchantShell } from "../../components/MerchantShell";
import { RiyalSymbol } from "../../components/RiyalSymbol";
import { supabase } from "../../lib/supabase";

type LoanStatus = "pending_analysis" | "analyzing" | "approved" | "denied" | "manual_review";

type Loan = {
  id: string;
  merchant_id: string;
  amount_requested: number;
  approved_amount: number | null;
  amount_paid: number | null;
  item_description: string;
  repayment_months: number;
  repayment_frequency: string;
  status: LoanStatus;
  synthesis_status: "pending" | "running" | "done" | "error" | null;
  decision_payload: {
    reasoning?: string;
    merchant_message?: string;
  } | null;
  created_at: string;
};

type DimensionResult = {
  id: string;
  loan_id: string;
  dimension: "pos" | "financial_docs" | "simah" | "sentiment" | "industry";
  status: "queued" | "processing" | "done" | "error" | "skipped";
  score: number | null;
  confidence: number | null;
  narrative: string | null;
  error_message: string | null;
};

type Document = {
  id: string;
  loan_id: string;
  doc_type: "bank_statement" | "financial_statement" | "pos_data" | "invoice";
  analysis_status: "pending" | "done" | "error";
  storage_path: string;
};

type Installment = {
  id: string;
  loan_id: string;
  installment_number: number;
  due_date: string;
  amount_sar: number;
  status: "pending" | "paid" | "overdue" | "cancelled";
  paid_at: string | null;
  stream_payment_url: string | null;
};

const DIM_LABELS: Record<DimensionResult["dimension"], string> = {
  pos: "Sales health",
  financial_docs: "Can afford",
  simah: "Business trust",
  sentiment: "Customer reviews",
  industry: "Industry outlook",
};

export function MerchantLoanDetail() {
  const { id } = useParams<{ id: string }>();
  const loanId = id!;
  const [loan, setLoan] = useState<Loan | null>(null);
  const [dims, setDims] = useState<DimensionResult[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [installments, setInstallments] = useState<Installment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [loanQ, dimQ, docQ, instQ] = await Promise.all([
        supabase.from("loans").select("*").eq("id", loanId).maybeSingle(),
        supabase.from("dimension_results").select("*").eq("loan_id", loanId),
        supabase.from("documents").select("*").eq("loan_id", loanId),
        supabase.from("installments").select("*").eq("loan_id", loanId).order("installment_number"),
      ]);
      if (cancelled) return;
      setLoan((loanQ.data as Loan | null) ?? null);
      setDims((dimQ.data as DimensionResult[] | null) ?? []);
      setDocuments((docQ.data as Document[] | null) ?? []);
      setInstallments((instQ.data as Installment[] | null) ?? []);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [loanId]);

  // Fallback poll for documents — `documents` isn't on the supabase_realtime
  // publication, so analysis_status flips won't push. Poll every 3s while the
  // loan is still analyzing. Loans/dims/installments are on the publication and
  // push via Realtime below.
  useEffect(() => {
    if (!loan) return;
    if (["approved", "denied", "manual_review"].includes(loan.status)) return;
    const interval = setInterval(async () => {
      const { data } = await supabase.from("documents").select("*").eq("loan_id", loanId);
      if (data) setDocuments(data as Document[]);
    }, 3000);
    return () => clearInterval(interval);
  }, [loan, loanId]);

  useEffect(() => {
    const loanCh = supabase
      .channel(`loan:${loanId}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "loans", filter: `id=eq.${loanId}` },
        (payload) => setLoan(payload.new as Loan),
      )
      .subscribe();

    const dimCh = supabase
      .channel(`dims:${loanId}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "dimension_results", filter: `loan_id=eq.${loanId}` },
        (payload) => {
          const row = payload.new as DimensionResult;
          setDims((cur) => {
            const idx = cur.findIndex((d) => d.id === row.id);
            if (idx === -1) return [...cur, row];
            const copy = [...cur];
            copy[idx] = row;
            return copy;
          });
        },
      )
      .subscribe();

    const docCh = supabase
      .channel(`docs:${loanId}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "documents", filter: `loan_id=eq.${loanId}` },
        (payload) => {
          const row = payload.new as Document;
          setDocuments((cur) => {
            const idx = cur.findIndex((d) => d.id === row.id);
            if (idx === -1) return [...cur, row];
            const copy = [...cur];
            copy[idx] = row;
            return copy;
          });
        },
      )
      .subscribe();

    const instCh = supabase
      .channel(`inst:${loanId}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "installments", filter: `loan_id=eq.${loanId}` },
        (payload) => {
          const row = payload.new as Installment;
          setInstallments((cur) => {
            const idx = cur.findIndex((i) => i.id === row.id);
            if (idx === -1) return [...cur, row].sort((a, b) => a.installment_number - b.installment_number);
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
      supabase.removeChannel(docCh);
      supabase.removeChannel(instCh);
    };
  }, [loanId]);

  if (loading) {
    return (
      <MerchantShell>
        <div className="font-mono text-xs uppercase tracking-widest text-on-surface-variant">
          Loading lease&hellip;
        </div>
      </MerchantShell>
    );
  }

  if (!loan) {
    return (
      <MerchantShell>
        <div className="bg-white border-[3px] border-black offset-shadow p-8">
          <h2 className="text-2xl font-black uppercase mb-3">Lease not found</h2>
          <Link to="/merchant/dashboard" className="font-mono text-xs font-bold uppercase underline">
            Back to dashboard →
          </Link>
        </div>
      </MerchantShell>
    );
  }

  const isDecided = ["approved", "denied", "manual_review"].includes(loan.status);

  return (
    <MerchantShell>
      <div className="mb-8">
        <div className="font-mono text-xs font-bold uppercase tracking-widest text-on-surface-variant flex items-center gap-3">
          <span className="w-8 h-[3px] bg-black" />
          Lease · #{loan.id.slice(0, 8)}
        </div>
        <h1 className="mt-4 text-5xl font-black tracking-tighter uppercase">
          {loan.item_description || "Your lease"}
        </h1>
      </div>

      {!isDecided ? (
        <AnalyzingView loan={loan} dims={dims} documents={documents} />
      ) : (
        <DecidedView loan={loan} installments={installments} />
      )}
    </MerchantShell>
  );
}

/* ─── ANALYZING ─────────────────────────────────────────────────────────── */

function AnalyzingView({
  loan, dims, documents,
}: {
  loan: Loan;
  dims: DimensionResult[];
  documents: Document[];
}) {
  const docsDone = documents.filter((d) => d.analysis_status === "done").length;
  const docsTotal = documents.length || 1;
  const dimsDone = dims.filter((d) => d.status === "done" || d.status === "skipped").length;
  const dimsTotal = 5;
  const synthState = loan.synthesis_status ?? "pending";

  const overallPct = useMemo(() => {
    const extractionPct = (docsDone / docsTotal) * 0.3;
    const dimsPct = (dimsDone / dimsTotal) * 0.5;
    const synthesisPct = synthState === "done" ? 0.2 : synthState === "running" ? 0.1 : 0;
    return Math.min(100, Math.round((extractionPct + dimsPct + synthesisPct) * 100));
  }, [docsDone, docsTotal, dimsDone, synthState]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
      <div className="lg:col-span-5 space-y-6">
        <div className="bg-white border-[3px] border-black offset-shadow-md p-6">
          <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
            Requested
          </div>
          <div className="mt-2 font-display text-5xl font-black flex items-baseline gap-3">
            <RiyalSymbol className="h-[0.75em] w-[0.68em] translate-y-[0.05em]" />
            <span>{loan.amount_requested.toLocaleString("en-US")}</span>
          </div>
          <div className="mt-2 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
            {loan.repayment_months} months · {loan.repayment_frequency}
          </div>
        </div>

        <div className="bg-secondary text-white border-[3px] border-black offset-shadow-md p-6">
          <div className="font-mono text-[10px] uppercase tracking-widest opacity-80 mb-3">
            Engine status
          </div>
          <div className="font-display text-3xl font-black leading-none">
            Analyzing…
          </div>
          <div className="mt-3 font-mono text-xs uppercase tracking-widest opacity-80">
            {overallPct}% complete
          </div>
          <div className="mt-4 h-2 bg-white/20 border-[2px] border-black">
            <div
              className="h-full bg-primary-container transition-[width] duration-500"
              style={{ width: `${overallPct}%` }}
            />
          </div>
          <div className="mt-5 font-mono text-xs opacity-80 leading-relaxed">
            This usually takes 60-90 seconds. It&apos;s okay to close this page — we&apos;ll email
            you the outcome.
          </div>
        </div>

        <div className="bg-white border-[3px] border-black offset-shadow p-6">
          <div className="font-mono text-[10px] font-bold uppercase tracking-widest mb-3">
            Documents ({docsDone}/{docsTotal})
          </div>
          <div className="space-y-2">
            {documents.map((d) => (
              <div key={d.id} className="flex items-center justify-between text-sm">
                <span className="font-mono text-xs uppercase tracking-widest text-on-surface-variant">
                  {d.doc_type.replace(/_/g, " ")}
                </span>
                <StatusChip status={d.analysis_status} />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="lg:col-span-7">
        <TerminalProgress dims={dims} synthStatus={synthState} />
      </div>
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const color =
    status === "done" ? "bg-success text-white"
    : status === "processing" || status === "running" ? "bg-primary-container text-black animate-pulse"
    : status === "error" ? "bg-error text-white"
    : "bg-surface-container text-on-surface-variant";
  return (
    <span className={`font-mono text-[10px] font-bold uppercase tracking-widest px-2 py-1 border-[3px] border-black ${color}`}>
      {status}
    </span>
  );
}

function TerminalProgress({ dims, synthStatus }: { dims: DimensionResult[]; synthStatus: string }) {
  const allDims: Array<DimensionResult["dimension"]> = ["pos", "financial_docs", "simah", "sentiment", "industry"];
  const dimMap = new Map(dims.map((d) => [d.dimension, d]));

  return (
    <div className="bg-black border-[3px] border-black offset-shadow-lg w-full flex flex-col overflow-hidden">
      <div className="bg-secondary border-b-[3px] border-black p-3 flex items-center justify-between">
        <div className="flex gap-2">
          <div className="w-3 h-3 bg-white border border-black" />
          <div className="w-3 h-3 bg-white border border-black opacity-50" />
          <div className="w-3 h-3 bg-white border border-black opacity-20" />
        </div>
        <div className="font-mono text-[10px] text-white font-bold tracking-widest">
          UNDERWRITING.LIVE
        </div>
      </div>
      <div className="p-6 font-mono text-sm flex-grow scanline">
        <div className="mb-4 text-white/60">
          <span className="text-green-400"># </span> Running 5-dimension underwrite…
        </div>

        <div className="space-y-3 mb-6">
          {allDims.map((dimKey) => {
            const d = dimMap.get(dimKey);
            const status = d?.status ?? "queued";
            const label = DIM_LABELS[dimKey];
            const isRunning = status === "processing";
            const color =
              status === "done" ? "text-green-400"
              : isRunning ? "text-[#FDC800]"
              : status === "error" ? "text-red-400"
              : status === "skipped" ? "text-white/20 line-through"
              : "text-white/30";
            const icon =
              status === "done" ? "✓"
              : isRunning ? "●"
              : status === "error" ? "✕"
              : status === "skipped" ? "∼"
              : "—";
            return (
              <div key={dimKey} className="flex items-center gap-3">
                <span className={`${color} w-4 ${isRunning ? "animate-pulse" : ""}`}>
                  {icon}
                </span>
                <span className="text-white/80 flex-1">{label}</span>
                <span className={`${color} text-xs uppercase tracking-widest`}>{status}</span>
                {d?.score != null && (
                  <span className="text-white font-bold w-12 text-right tabular-nums">
                    {d.score}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        <div className="border-t-[2px] border-white/20 pt-4">
          <div className="flex items-center gap-3">
            <span
              className={`w-4 ${
                synthStatus === "done" ? "text-green-400"
                : synthStatus === "running" ? "text-[#FDC800] animate-pulse"
                : "text-white/30"
              }`}
            >
              {synthStatus === "done" ? "✓" : synthStatus === "running" ? "●" : "—"}
            </span>
            <span className="text-white/80 flex-1">Final synthesis</span>
            <span className="text-white/60 text-xs uppercase tracking-widest">{synthStatus}</span>
          </div>
        </div>

        {synthStatus === "done" && (
          <div className="mt-6 inline-block bg-green-500 text-black px-2 py-1 font-black text-xs animate-pulse uppercase tracking-widest">
            &gt; Decision ready
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── DECIDED ──────────────────────────────────────────────────────────── */

function DecidedView({ loan, installments }: { loan: Loan; installments: Installment[] }) {
  if (loan.status === "approved") return <ApprovedView loan={loan} installments={installments} />;
  if (loan.status === "denied") return <DeniedView loan={loan} />;
  return <ManualReviewView loan={loan} />;
}

function ApprovedView({ loan, installments }: { loan: Loan; installments: Installment[] }) {
  const approvedAmount = loan.approved_amount ?? loan.amount_requested;

  return (
    <div className="space-y-8">
      <div className="bg-success text-white border-[3px] border-black offset-shadow-lg p-10 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-32 h-32 border-r-[3px] border-b-[3px] border-white opacity-10" />
        <div className="absolute bottom-0 right-0 w-64 h-64 border-l-[3px] border-t-[3px] border-white opacity-10" />
        <div className="relative z-10">
          <div className="font-mono text-xs font-bold uppercase tracking-widest opacity-80 mb-3">
            Status · Approved
          </div>
          <div className="flex flex-col md:flex-row md:items-end gap-6 justify-between">
            <div>
              <div className="font-display text-7xl font-black leading-none flex items-baseline gap-3">
                <RiyalSymbol className="h-[0.75em] w-[0.68em] translate-y-[0.05em]" />
                <span>{approvedAmount.toLocaleString("en-US")}</span>
              </div>
              <div className="mt-3 font-mono text-xs uppercase tracking-widest opacity-80">
                Funded · {loan.repayment_months} months · auto-debit
              </div>
            </div>
            {installments.length > 0 && (
              <div className="text-right">
                <div className="font-mono text-[10px] uppercase tracking-widest opacity-80">
                  Next payment
                </div>
                <div className="mt-1 font-display text-3xl font-black flex items-baseline gap-2 justify-end">
                  <RiyalSymbol className="h-[0.7em] w-[0.63em] translate-y-[0.05em]" />
                  <span>{installments[0].amount_sar.toLocaleString("en-US")}</span>
                </div>
                <div className="mt-1 font-mono text-[10px] uppercase tracking-widest opacity-80">
                  Due {new Date(installments[0].due_date).toLocaleDateString()}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {installments.length > 0 && (
        <div className="bg-white border-[3px] border-black offset-shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="font-mono text-[10px] font-bold uppercase tracking-widest">
              Repayment schedule
            </div>
            <Link
              to="/merchant/payments"
              className="font-mono text-[10px] font-bold uppercase tracking-widest underline"
            >
              Full schedule →
            </Link>
          </div>
          <div className="space-y-2">
            {installments.slice(0, 6).map((inst) => (
              <InstallmentRow key={inst.id} inst={inst} />
            ))}
            {installments.length > 6 && (
              <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant pt-2">
                · · · {installments.length - 6} more
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function InstallmentRow({ inst }: { inst: Installment }) {
  const paid = inst.status === "paid";
  return (
    <div className="flex items-center justify-between text-sm font-mono">
      <span className="text-on-surface-variant w-10">#{String(inst.installment_number).padStart(2, "0")}</span>
      <span className="text-on-surface-variant flex-1">
        {new Date(inst.due_date).toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "numeric" })}
      </span>
      <span className="font-bold tabular-nums w-24 text-right flex items-baseline justify-end gap-1">
        <RiyalSymbol className="h-[0.8em] w-[0.72em] translate-y-[0.05em]" />
        <span>{inst.amount_sar.toLocaleString("en-US")}</span>
      </span>
      <span
        className={`ml-4 text-[10px] font-black uppercase tracking-widest px-2 py-1 border-[3px] border-black w-24 text-center ${
          paid ? "bg-success text-white"
          : inst.status === "overdue" ? "bg-error text-white"
          : "bg-white"
        }`}
      >
        {paid ? "✓ paid" : inst.status === "overdue" ? "overdue" : "pending"}
      </span>
    </div>
  );
}

function DeniedView({ loan }: { loan: Loan }) {
  const reason = loan.decision_payload?.merchant_message ?? loan.decision_payload?.reasoning ?? "We weren't able to approve this application at this time.";
  return (
    <div className="bg-error text-white border-[3px] border-black offset-shadow-lg p-10 relative overflow-hidden">
      <div className="relative z-10">
        <div className="font-mono text-xs font-bold uppercase tracking-widest opacity-80 mb-3">
          Status · Not approved
        </div>
        <h2 className="font-display text-5xl font-black tracking-tighter uppercase leading-[0.9] max-w-2xl">
          We can&apos;t fund this one.
        </h2>
        <p className="mt-6 text-lg max-w-xl opacity-90 leading-snug">{reason}</p>
        <div className="mt-8 flex gap-3">
          <Link
            to="/merchant/dashboard"
            className="bg-white text-black border-[3px] border-black px-6 py-3 font-mono font-black uppercase text-sm offset-shadow hover-lift"
          >
            Back to dashboard
          </Link>
          <Link
            to="/merchant/new-loan"
            className="bg-primary-container text-black border-[3px] border-black px-6 py-3 font-mono font-black uppercase text-sm offset-shadow hover-lift"
          >
            Try a new application
          </Link>
        </div>
      </div>
    </div>
  );
}

function ManualReviewView({ loan }: { loan: Loan }) {
  return (
    <div className="bg-primary-container text-black border-[3px] border-black offset-shadow-lg p-10 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-32 h-32 border-r-[3px] border-b-[3px] border-black opacity-10" />
      <div className="absolute bottom-0 right-0 w-64 h-64 border-l-[3px] border-t-[3px] border-black opacity-10" />
      <div className="relative z-10">
        <div className="font-mono text-xs font-bold uppercase tracking-widest opacity-70 mb-3">
          Status · In review
        </div>
        <h2 className="font-display text-5xl font-black tracking-tighter uppercase leading-[0.9] max-w-2xl">
          A human will take a look.
        </h2>
        <p className="mt-6 text-lg max-w-xl opacity-90 leading-snug">
          Your application looks strong, but one or two of our checks want a human eye. Our team will
          review within 24 hours and email you a decision. You asked for{" "}
          <span className="font-black whitespace-nowrap">
            <RiyalSymbol className="h-[0.75em] w-[0.68em] translate-y-[0.05em] inline-block" /> {loan.amount_requested.toLocaleString("en-US")}
          </span>
          ; the reviewer may come back with a counter-offer.
        </p>
      </div>
    </div>
  );
}

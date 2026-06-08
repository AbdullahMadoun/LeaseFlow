import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AdminShell } from "../../components/AdminShell";
import { RiyalSymbol } from "../../components/RiyalSymbol";
import { supabase, type RiskSnapshot } from "../../lib/supabase";
import { api } from "../../lib/api";

type Loan = {
  id: string;
  merchant_id: string;
  amount_requested: number;
  approved_amount: number | null;
  item_description: string;
  status: "pending_analysis" | "analyzing" | "approved" | "denied" | "manual_review";
  synthesis_status: "pending" | "running" | "done" | "error" | null;
  created_at: string;
  repayment_months: number;
};

type Merchant = {
  id: string;
  business_name: string;
};

const ALL_STATUSES: Array<{ key: "all" | Loan["status"]; label: string }> = [
  { key: "manual_review",    label: "Manual review" },
  { key: "analyzing",        label: "Analyzing" },
  { key: "pending_analysis", label: "Pending" },
  { key: "approved",         label: "Approved" },
  { key: "denied",           label: "Denied" },
  { key: "all",              label: "All" },
];

export function AdminPipeline() {
  const [loans, setLoans] = useState<Loan[]>([]);
  const [merchants, setMerchants] = useState<Map<string, Merchant>>(new Map());
  const [filter, setFilter] = useState<"all" | Loan["status"]>("manual_review");
  const [risk, setRisk] = useState<RiskSnapshot | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [{ data: loanData }, { data: merchData }] = await Promise.all([
        supabase.from("loans").select("*").order("created_at", { ascending: false }).limit(200),
        supabase.from("merchants").select("id, business_name"),
      ]);
      if (cancelled) return;
      setLoans((loanData as Loan[] | null) ?? []);
      setMerchants(new Map(((merchData as Merchant[] | null) ?? []).map((m) => [m.id, m])));
      setLoading(false);

      try {
        const r = await api.currentRisk();
        if (!cancelled) setRisk(r.snapshot ?? null);
      } catch {
        // risk endpoint optional
      }
    })();

    const ch = supabase
      .channel("admin:loans")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "loans" },
        (payload) => {
          const row = payload.new as Loan;
          setLoans((cur) => {
            const idx = cur.findIndex((l) => l.id === row.id);
            if (idx === -1) return [row, ...cur];
            const copy = [...cur];
            copy[idx] = row;
            return copy;
          });
        },
      )
      .subscribe();

    return () => {
      cancelled = true;
      supabase.removeChannel(ch);
    };
  }, []);

  const filtered = useMemo(() => {
    if (filter === "all") return loans;
    return loans.filter((l) => l.status === filter);
  }, [loans, filter]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: loans.length };
    for (const l of loans) c[l.status] = (c[l.status] ?? 0) + 1;
    return c;
  }, [loans]);

  return (
    <AdminShell activeTab="pipeline">
      {risk && <RiskBanner risk={risk} />}

      <div className="mb-10">
        <div className="font-mono text-xs font-bold uppercase tracking-widest text-on-surface-variant flex items-center gap-3">
          <span className="w-8 h-[3px] bg-black" />
          Pipeline feed
        </div>
        <h1 className="mt-4 text-5xl font-black tracking-tighter uppercase">
          Underwriting queue
        </h1>
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        {ALL_STATUSES.map((s) => (
          <button
            key={s.key}
            onClick={() => setFilter(s.key)}
            className={`font-mono text-[10px] font-black uppercase tracking-widest px-3 py-2 border-[3px] border-black transition-colors ${
              filter === s.key
                ? "bg-primary-container text-black offset-shadow"
                : "bg-white hover:bg-surface-container-high"
            }`}
          >
            {s.label} · {counts[s.key === "all" ? "all" : s.key] ?? 0}
          </button>
        ))}
      </div>

      <div className="bg-white border-[3px] border-black offset-shadow">
        <div className="grid grid-cols-12 gap-4 items-center p-4 border-b-[3px] border-black bg-surface-container-low font-mono text-[10px] font-black uppercase tracking-widest">
          <div className="col-span-4">Merchant · ID</div>
          <div className="col-span-3">Amount</div>
          <div className="col-span-2">Term</div>
          <div className="col-span-2">Received</div>
          <div className="col-span-1 text-right">Status</div>
        </div>
        {loading ? (
          <div className="p-8 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
            Loading&hellip;
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center font-mono text-xs uppercase tracking-widest text-on-surface-variant">
            Nothing in this filter.
          </div>
        ) : (
          <div className="divide-y-[3px] divide-black">
            {filtered.map((l) => (
              <Row key={l.id} loan={l} merchant={merchants.get(l.merchant_id)} />
            ))}
          </div>
        )}
      </div>
    </AdminShell>
  );
}

function Row({ loan, merchant }: { loan: Loan; merchant?: Merchant }) {
  const amount = loan.approved_amount ?? loan.amount_requested;
  return (
    <Link
      to={`/admin/loans/${loan.id}`}
      className="grid grid-cols-12 gap-4 items-center p-4 hover:bg-surface-container-low transition-colors"
    >
      <div className="col-span-4 min-w-0">
        <div className="font-bold truncate">{merchant?.business_name ?? "Unknown merchant"}</div>
        <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant truncate">
          #{loan.id.slice(0, 8)} · {loan.item_description}
        </div>
      </div>
      <div className="col-span-3 font-display text-2xl font-black flex items-baseline gap-2">
        <RiyalSymbol className="h-[0.75em] w-[0.68em] translate-y-[0.05em]" />
        <span>{amount.toLocaleString("en-US")}</span>
      </div>
      <div className="col-span-2 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
        {loan.repayment_months} months
      </div>
      <div className="col-span-2 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
        {new Date(loan.created_at).toLocaleDateString("en-GB", { month: "short", day: "numeric" })}
      </div>
      <div className="col-span-1 text-right">
        <StatusChip status={loan.status} />
      </div>
    </Link>
  );
}

function StatusChip({ status }: { status: Loan["status"] }) {
  const map: Record<Loan["status"], string> = {
    pending_analysis: "bg-white",
    analyzing: "bg-primary-container animate-pulse",
    manual_review: "bg-warning text-white",
    approved: "bg-success text-white",
    denied: "bg-error text-white",
  };
  return (
    <span className={`font-mono text-[10px] font-black uppercase tracking-widest px-2 py-1 border-[3px] border-black ${map[status]}`}>
      {status.replace("_", " ")}
    </span>
  );
}

function RiskBanner({ risk }: { risk: RiskSnapshot }) {
  const tone =
    risk.market_status === "high_risk" ? "bg-error"
    : risk.market_status === "medium_risk" ? "bg-warning"
    : "bg-success";
  const label =
    risk.market_status === "high_risk" ? "HIGH RISK"
    : risk.market_status === "medium_risk" ? "MEDIUM RISK"
    : "LOW RISK";
  return (
    <div className={`${tone} text-white border-[3px] border-black offset-shadow p-4 mb-6 flex items-center justify-between gap-4`}>
      <div className="min-w-0">
        <div className="font-mono text-[10px] font-black uppercase tracking-widest opacity-80">
          Market · {label} · Appetite {risk.risk_appetite}
        </div>
        <div className="font-bold mt-1 truncate">
          {risk.market_notes || "Within tolerances"}
        </div>
      </div>
      <Link
        to="/admin/risk"
        className="bg-white text-black border-[3px] border-black px-4 py-2 font-mono text-[10px] font-black uppercase tracking-widest hover-lift shrink-0"
      >
        Risk detail →
      </Link>
    </div>
  );
}

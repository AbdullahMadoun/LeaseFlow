import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { MerchantShell } from "../../components/MerchantShell";
import { RiyalSymbol } from "../../components/RiyalSymbol";
import { supabase } from "../../lib/supabase";
import { useMerchant } from "../../hooks/useMerchant";

type Loan = {
  id: string;
  amount_requested: number;
  approved_amount: number | null;
  amount_paid: number | null;
  item_description: string;
  status: "pending_analysis" | "analyzing" | "approved" | "denied" | "manual_review";
  created_at: string;
  repayment_months: number;
};

type Installment = {
  id: string;
  loan_id: string;
  installment_number: number;
  due_date: string;
  amount_sar: number;
  status: "pending" | "paid" | "overdue" | "failed";
};

const STATUS_LABELS: Record<Loan["status"], string> = {
  pending_analysis: "Awaiting docs",
  analyzing: "Analyzing…",
  approved: "Approved",
  denied: "Not approved",
  manual_review: "In review",
};

const STATUS_COLORS: Record<Loan["status"], string> = {
  pending_analysis: "bg-surface-container-high text-on-surface-variant",
  analyzing: "bg-primary-container text-black",
  approved: "bg-success text-white",
  denied: "bg-error text-white",
  manual_review: "bg-warning text-white",
};

export function MerchantDashboard() {
  const { merchant, loading: merchantLoading } = useMerchant();
  const [loans, setLoans] = useState<Loan[]>([]);
  const [nextInstallment, setNextInstallment] = useState<Installment | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!merchant) {
      setLoading(merchantLoading);
      return;
    }
    let cancelled = false;
    (async () => {
      const { data: loanData } = await supabase
        .from("loans")
        .select("*")
        .eq("merchant_id", merchant.id)
        .order("created_at", { ascending: false });
      if (cancelled) return;
      const ls = (loanData as Loan[] | null) ?? [];
      setLoans(ls);

      const activeIds = ls.filter((l) => l.status === "approved").map((l) => l.id);
      if (activeIds.length > 0) {
        const { data: instData } = await supabase
          .from("installments")
          .select("*")
          .in("loan_id", activeIds)
          .eq("status", "pending")
          .order("due_date", { ascending: true })
          .limit(1);
        if (!cancelled) setNextInstallment(((instData as Installment[] | null) ?? [])[0] ?? null);
      }
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [merchant, merchantLoading]);

  useEffect(() => {
    if (!merchant) return;
    const ch = supabase
      .channel(`loans:${merchant.id}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "loans", filter: `merchant_id=eq.${merchant.id}` },
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
      supabase.removeChannel(ch);
    };
  }, [merchant]);

  return (
    <MerchantShell activeTab="dashboard">
      <div className="mb-10 flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="font-mono text-xs font-bold uppercase tracking-widest text-on-surface-variant flex items-center gap-3">
            <span className="w-8 h-[3px] bg-black" />
            Merchant dashboard
          </div>
          <h1 className="mt-4 text-5xl font-black tracking-tighter uppercase">
            Your ledger
          </h1>
        </div>
        <Link
          to="/merchant/new-loan"
          className="bg-primary-container border-[3px] border-black px-6 py-3 font-mono font-black uppercase text-sm offset-shadow hover-lift flex items-center gap-3"
        >
          Start new lease
          <span className="material-symbols-outlined">add</span>
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
        <div className="bg-white border-[3px] border-black offset-shadow p-6">
          <div className="font-mono text-[10px] font-bold uppercase tracking-widest mb-2">
            Active leases
          </div>
          <div className="font-display text-5xl font-black">
            {loans.filter((l) => l.status === "approved").length}
          </div>
        </div>
        <div className="bg-white border-[3px] border-black offset-shadow p-6">
          <div className="font-mono text-[10px] font-bold uppercase tracking-widest mb-2">
            In progress
          </div>
          <div className="font-display text-5xl font-black">
            {loans.filter((l) => ["pending_analysis", "analyzing", "manual_review"].includes(l.status)).length}
          </div>
        </div>
        <div className="bg-secondary text-white border-[3px] border-black offset-shadow p-6">
          <div className="font-mono text-[10px] uppercase tracking-widest opacity-80 mb-2">
            Next payment
          </div>
          {nextInstallment ? (
            <>
              <div className="font-display text-4xl font-black flex items-baseline gap-2">
                <RiyalSymbol className="h-[0.72em] w-[0.65em] translate-y-[0.05em]" />
                <span>{nextInstallment.amount_sar.toLocaleString("en-US")}</span>
              </div>
              <div className="mt-1 font-mono text-xs uppercase tracking-widest opacity-80">
                Due {new Date(nextInstallment.due_date).toLocaleDateString("en-GB", {
                  month: "short", day: "numeric", year: "numeric",
                })}
              </div>
            </>
          ) : (
            <div className="font-mono text-xs uppercase tracking-widest opacity-70">
              Nothing due
            </div>
          )}
        </div>
      </div>

      <div className="bg-white border-[3px] border-black offset-shadow">
        <div className="flex items-center justify-between p-5 border-b-[3px] border-black">
          <div className="font-mono text-xs font-bold uppercase tracking-widest">
            Your leases ({loans.length})
          </div>
        </div>
        {loading ? (
          <div className="p-8 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
            Loading&hellip;
          </div>
        ) : loans.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="divide-y-[3px] divide-black">
            {loans.map((l) => (
              <LoanRow key={l.id} loan={l} />
            ))}
          </div>
        )}
      </div>
    </MerchantShell>
  );
}

function LoanRow({ loan }: { loan: Loan }) {
  const amount = loan.approved_amount ?? loan.amount_requested;
  return (
    <Link
      to={`/merchant/loans/${loan.id}`}
      className="grid grid-cols-12 gap-4 items-center p-5 hover:bg-surface-container-low transition-colors"
    >
      <div className="col-span-12 md:col-span-5">
        <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
          #{loan.id.slice(0, 8)} · {new Date(loan.created_at).toLocaleDateString()}
        </div>
        <div className="mt-1 text-lg font-bold truncate">{loan.item_description || "Unspecified"}</div>
      </div>
      <div className="col-span-6 md:col-span-3 flex items-baseline gap-2">
        <RiyalSymbol className="h-[0.75em] w-[0.68em] translate-y-[0.05em]" />
        <span className="font-display text-2xl font-black">{amount.toLocaleString("en-US")}</span>
      </div>
      <div className="col-span-3 md:col-span-2 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
        {loan.repayment_months} mo
      </div>
      <div className="col-span-3 md:col-span-2 flex justify-end">
        <span
          className={`font-mono text-[10px] font-black uppercase tracking-widest px-3 py-1 border-[3px] border-black ${STATUS_COLORS[loan.status]}`}
        >
          {STATUS_LABELS[loan.status]}
        </span>
      </div>
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="p-12 text-center">
      <span className="material-symbols-outlined text-5xl text-on-surface-variant">inbox</span>
      <div className="mt-3 text-xl font-black uppercase">No leases yet</div>
      <p className="mt-2 text-on-surface-variant">
        Apply for your first lease and see it here in real time.
      </p>
      <Link
        to="/merchant/new-loan"
        className="inline-flex items-center gap-3 mt-6 bg-primary-container border-[3px] border-black px-6 py-3 font-mono font-black uppercase text-sm offset-shadow hover-lift"
      >
        Start new lease
        <span className="material-symbols-outlined">arrow_forward</span>
      </Link>
    </div>
  );
}

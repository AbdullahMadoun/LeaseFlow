import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { MerchantShell } from "../../components/MerchantShell";
import { RiyalSymbol } from "../../components/RiyalSymbol";
import { supabase } from "../../lib/supabase";
import { useMerchant } from "../../hooks/useMerchant";

type Installment = {
  id: string;
  loan_id: string;
  installment_number: number;
  due_date: string;
  amount_sar: number;
  paid_amount_sar: number | null;
  status: "pending" | "paid" | "overdue" | "cancelled";
  paid_at: string | null;
  stream_payment_url: string | null;
  payment_method: string | null;
};

type LoanLite = {
  id: string;
  item_description: string;
};

export function MerchantPayments() {
  const { merchant } = useMerchant();
  const [installments, setInstallments] = useState<Installment[]>([]);
  const [loansById, setLoansById] = useState<Map<string, LoanLite>>(new Map());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!merchant) return;
    let cancelled = false;
    (async () => {
      const { data: loanData } = await supabase
        .from("loans")
        .select("id, item_description")
        .eq("merchant_id", merchant.id);
      const ls = (loanData as LoanLite[] | null) ?? [];
      const map = new Map(ls.map((l) => [l.id, l]));
      if (cancelled) return;
      setLoansById(map);

      if (ls.length === 0) {
        setInstallments([]);
        setLoading(false);
        return;
      }

      const { data: instData } = await supabase
        .from("installments")
        .select("*")
        .in("loan_id", ls.map((l) => l.id))
        .order("due_date", { ascending: true });
      if (cancelled) return;
      setInstallments((instData as Installment[] | null) ?? []);
      setLoading(false);
    })();

    const loanIdsForSub = Array.from(loansById.keys());
    const ch = supabase
      .channel(`installments:merchant:${merchant.id}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "installments" },
        (payload) => {
          const row = payload.new as Installment;
          if (loanIdsForSub.length > 0 && !loanIdsForSub.includes(row.loan_id)) return;
          setInstallments((cur) => {
            const idx = cur.findIndex((i) => i.id === row.id);
            if (idx === -1) return [...cur, row].sort((a, b) => a.due_date.localeCompare(b.due_date));
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [merchant]);

  const totals = useMemo(() => {
    const paid = installments.filter((i) => i.status === "paid");
    const pending = installments.filter((i) => i.status === "pending");
    const overdue = installments.filter((i) => i.status === "overdue");
    const paidSum = paid.reduce((s, i) => s + (i.paid_amount_sar ?? i.amount_sar), 0);
    const pendingSum = pending.reduce((s, i) => s + i.amount_sar, 0);
    return { paid, pending, overdue, paidSum, pendingSum };
  }, [installments]);

  return (
    <MerchantShell activeTab="payments">
      <div className="mb-10">
        <div className="font-mono text-xs font-bold uppercase tracking-widest text-on-surface-variant flex items-center gap-3">
          <span className="w-8 h-[3px] bg-black" />
          Payments
        </div>
        <h1 className="mt-4 text-5xl font-black tracking-tighter uppercase">Your schedule</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <SummaryCard label="Paid" count={totals.paid.length} sum={totals.paidSum} tone="success" />
        <SummaryCard label="Due" count={totals.pending.length} sum={totals.pendingSum} tone="warning" />
        <SummaryCard label="Overdue" count={totals.overdue.length} sum={totals.overdue.reduce((s, i) => s + i.amount_sar, 0)} tone="error" />
      </div>

      <div className="bg-white border-[3px] border-black offset-shadow">
        <div className="p-5 border-b-[3px] border-black font-mono text-xs font-bold uppercase tracking-widest">
          All installments ({installments.length})
        </div>
        {loading ? (
          <div className="p-8 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
            Loading&hellip;
          </div>
        ) : installments.length === 0 ? (
          <EmptyPayments />
        ) : (
          <div className="divide-y-[3px] divide-black">
            {installments.map((i) => (
              <InstallmentRow key={i.id} inst={i} loan={loansById.get(i.loan_id)} />
            ))}
          </div>
        )}
      </div>
    </MerchantShell>
  );
}

function SummaryCard({
  label, count, sum, tone,
}: {
  label: string;
  count: number;
  sum: number;
  tone: "success" | "warning" | "error";
}) {
  const toneMap = {
    success: "bg-success text-white",
    warning: "bg-primary-container text-black",
    error: "bg-error text-white",
  };
  return (
    <div className={`border-[3px] border-black offset-shadow p-6 ${toneMap[tone]}`}>
      <div className="font-mono text-[10px] uppercase tracking-widest opacity-80 mb-2">
        {label} · {count}
      </div>
      <div className="font-display text-4xl font-black flex items-baseline gap-2">
        <RiyalSymbol className="h-[0.72em] w-[0.65em] translate-y-[0.05em]" />
        <span>{sum.toLocaleString("en-US", { maximumFractionDigits: 0 })}</span>
      </div>
    </div>
  );
}

function InstallmentRow({ inst, loan }: { inst: Installment; loan?: LoanLite }) {
  const paid = inst.status === "paid";
  const overdue = inst.status === "overdue";
  return (
    <div className="grid grid-cols-12 gap-4 items-center p-5">
      <div className="col-span-12 md:col-span-4 min-w-0">
        <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant truncate">
          {loan?.item_description ?? "Lease"} · #
          {String(inst.installment_number).padStart(2, "0")}
        </div>
        <div className="mt-1 font-mono text-sm">
          Due{" "}
          {new Date(inst.due_date).toLocaleDateString("en-GB", {
            year: "numeric", month: "short", day: "numeric",
          })}
        </div>
      </div>
      <div className="col-span-6 md:col-span-3 font-display text-2xl font-black flex items-baseline gap-2">
        <RiyalSymbol className="h-[0.75em] w-[0.68em] translate-y-[0.05em]" />
        <span>{inst.amount_sar.toLocaleString("en-US")}</span>
      </div>
      <div className="col-span-6 md:col-span-2">
        <span
          className={`font-mono text-[10px] font-black uppercase tracking-widest px-3 py-1 border-[3px] border-black ${
            paid ? "bg-success text-white"
            : overdue ? "bg-error text-white"
            : "bg-white"
          }`}
        >
          {paid ? "✓ Paid" : overdue ? "Overdue" : "Pending"}
        </span>
      </div>
      <div className="col-span-12 md:col-span-3 flex md:justify-end gap-2">
        {paid ? (
          <span className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
            {inst.payment_method ?? "paid"} ·{" "}
            {inst.paid_at ? new Date(inst.paid_at).toLocaleDateString() : ""}
          </span>
        ) : inst.stream_payment_url ? (
          <a
            href={inst.stream_payment_url}
            target="_blank"
            rel="noopener noreferrer"
            className="bg-primary-container border-[3px] border-black px-4 py-2 font-mono text-xs font-black uppercase tracking-widest offset-shadow hover-lift inline-flex items-center gap-2"
          >
            Pay now
            <span className="material-symbols-outlined text-base">open_in_new</span>
          </a>
        ) : (
          <span className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
            Link unavailable
          </span>
        )}
      </div>
    </div>
  );
}

function EmptyPayments() {
  return (
    <div className="p-12 text-center">
      <span className="material-symbols-outlined text-5xl text-on-surface-variant">receipt_long</span>
      <div className="mt-3 text-xl font-black uppercase">No payments scheduled</div>
      <p className="mt-2 text-on-surface-variant">
        Your payment schedule will appear here after your first lease is approved.
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

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AdminShell } from "../../components/AdminShell";
import { supabase, type RiskSnapshot } from "../../lib/supabase";
import { api, ApiError } from "../../lib/api";

const MARKET_TONE: Record<RiskSnapshot["market_status"], string> = {
  low_risk: "bg-success text-white",
  medium_risk: "bg-warning text-white",
  high_risk: "bg-error text-white",
};

const MARKET_LABEL: Record<RiskSnapshot["market_status"], string> = {
  low_risk: "Low risk",
  medium_risk: "Medium risk",
  high_risk: "High risk",
};

const APPETITE_COPY: Record<RiskSnapshot["risk_appetite"], string> = {
  conservative: "Conservative · tighter thresholds",
  moderate: "Moderate · default policy",
  aggressive: "Aggressive · open to more review",
};

export function AdminRisk() {
  const [current, setCurrent] = useState<RiskSnapshot | null>(null);
  const [history, setHistory] = useState<RiskSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      const r = await api.currentRisk();
      setCurrent(r.snapshot ?? null);
    } catch {
      // optional endpoint
    }
    const { data } = await supabase
      .from("risk_snapshots")
      .select("*")
      .order("captured_at", { ascending: false })
      .limit(20);
    setHistory((data as RiskSnapshot[] | null) ?? []);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const r = await api.takeRiskSnapshot();
      setCurrent(r.snapshot);
      await load();
      toast.success("New snapshot captured");
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Snapshot failed";
      toast.error(msg);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <AdminShell activeTab="risk">
      <div className="mb-10 flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="font-mono text-xs font-bold uppercase tracking-widest text-on-surface-variant flex items-center gap-3">
            <span className="w-8 h-[3px] bg-black" />
            Risk policy
          </div>
          <h1 className="mt-4 text-5xl font-black tracking-tighter uppercase">
            Market &amp; appetite
          </h1>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="bg-primary-container border-[3px] border-black px-6 py-3 font-mono font-black uppercase text-sm offset-shadow hover-lift disabled:opacity-40"
        >
          {refreshing ? "Snapshotting…" : "Refresh snapshot"}
        </button>
      </div>

      {current ? (
        <div
          className={`${MARKET_TONE[current.market_status]} border-[3px] border-black offset-shadow-md p-8 mb-6`}
        >
          <div className="font-mono text-[10px] uppercase tracking-widest opacity-80 mb-2">
            Market · {new Date(current.captured_at).toLocaleString()}
          </div>
          <div className="font-display text-6xl font-black uppercase tracking-tighter">
            {MARKET_LABEL[current.market_status]}
          </div>
          {current.market_notes && (
            <p className="mt-4 text-lg max-w-3xl leading-snug">{current.market_notes}</p>
          )}
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="border-[3px] border-white/40 p-4">
              <div className="font-mono text-[10px] uppercase tracking-widest opacity-80">
                Appetite
              </div>
              <div className="mt-2 text-2xl font-black uppercase">{current.risk_appetite}</div>
              <div className="mt-1 font-mono text-[10px] opacity-80">
                {APPETITE_COPY[current.risk_appetite]}
              </div>
            </div>
            <div className="border-[3px] border-white/40 p-4">
              <div className="font-mono text-[10px] uppercase tracking-widest opacity-80">
                Cashflow score
              </div>
              <div className="mt-2 text-2xl font-black">
                {current.cashflow_score != null ? current.cashflow_score.toFixed(2) : "—"}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white border-[3px] border-black offset-shadow p-8 mb-6 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
          No snapshot yet. Click &quot;Refresh snapshot&quot; to capture one.
        </div>
      )}

      <div className="bg-white border-[3px] border-black offset-shadow">
        <div className="p-5 border-b-[3px] border-black font-mono text-xs font-bold uppercase tracking-widest">
          History
        </div>
        {loading ? (
          <div className="p-8 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
            Loading&hellip;
          </div>
        ) : history.length === 0 ? (
          <div className="p-8 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
            No snapshots yet.
          </div>
        ) : (
          <div className="divide-y-[3px] divide-black">
            {history.map((s) => (
              <div key={s.id} className="grid grid-cols-12 gap-4 items-center p-4">
                <div className="col-span-2">
                  <span
                    className={`font-mono text-[10px] font-black uppercase tracking-widest px-3 py-1 border-[3px] border-black ${MARKET_TONE[s.market_status]}`}
                  >
                    {MARKET_LABEL[s.market_status]}
                  </span>
                </div>
                <div className="col-span-2 font-mono text-xs uppercase tracking-widest">
                  {s.risk_appetite}
                </div>
                <div className="col-span-5 truncate text-sm text-on-surface-variant">
                  {s.market_notes ?? "—"}
                </div>
                <div className="col-span-3 text-right font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
                  {new Date(s.captured_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AdminShell>
  );
}

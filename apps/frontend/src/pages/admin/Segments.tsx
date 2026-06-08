import { useEffect, useState } from "react";
import { AdminShell } from "../../components/AdminShell";
import { supabase, type Segment } from "../../lib/supabase";

export function AdminSegments() {
  const [segments, setSegments] = useState<Segment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { data } = await supabase.from("segments").select("*").order("name");
      if (cancelled) return;
      setSegments((data as Segment[] | null) ?? []);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AdminShell activeTab="segments">
      <div className="mb-10">
        <div className="font-mono text-xs font-bold uppercase tracking-widest text-on-surface-variant flex items-center gap-3">
          <span className="w-8 h-[3px] bg-black" />
          Segment catalog
        </div>
        <h1 className="mt-4 text-5xl font-black tracking-tighter uppercase">F&amp;B benchmarks</h1>
      </div>

      {loading ? (
        <div className="font-mono text-xs uppercase tracking-widest text-on-surface-variant">
          Loading&hellip;
        </div>
      ) : segments.length === 0 ? (
        <div className="bg-white border-[3px] border-black offset-shadow p-8 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
          No segments configured.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {segments.map((s) => (
            <SegmentCard key={s.id} segment={s} />
          ))}
        </div>
      )}
    </AdminShell>
  );
}

function SegmentCard({ segment }: { segment: Segment }) {
  const entries = Object.entries(segment.benchmarks ?? {});
  return (
    <div className="bg-white border-[3px] border-black offset-shadow p-5">
      <div className="font-mono text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">
        {segment.name}
      </div>
      <div className="text-xl font-black uppercase tracking-tight mb-4">
        {segment.label ?? segment.name}
      </div>
      {entries.length === 0 ? (
        <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
          No benchmarks.
        </div>
      ) : (
        <dl className="grid grid-cols-2 gap-2 text-xs font-mono">
          {entries.slice(0, 6).map(([k, v]) => (
            <div key={k} className="border-[3px] border-black p-2">
              <dt className="text-[10px] uppercase tracking-widest text-on-surface-variant truncate">
                {k.replace(/_/g, " ")}
              </dt>
              <dd className="mt-1 font-black truncate">{String(formatValue(v))}</dd>
            </div>
          ))}
        </dl>
      )}
      <div className="mt-4 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
        Updated {new Date(segment.updated_at).toLocaleDateString()}
      </div>
    </div>
  );
}

function formatValue(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return v.toLocaleString("en-US");
  if (typeof v === "string" || typeof v === "boolean") return String(v);
  return JSON.stringify(v).slice(0, 40);
}

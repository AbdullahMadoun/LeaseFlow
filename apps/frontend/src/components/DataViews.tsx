import type { ReactNode } from "react";
import { RiyalSymbol } from "./RiyalSymbol";

/* Small shared building blocks for turning backend JSON blobs into readable
 * cards. Intentionally un-styled at the page level — these are the atoms
 * admin/LoanDetail composes. */

export function Card({
  label,
  children,
  tone = "white",
  action,
}: {
  label: string;
  children: ReactNode;
  tone?: "white" | "success" | "warning" | "error" | "secondary";
  action?: ReactNode;
}) {
  const bg = {
    white: "bg-white",
    success: "bg-success text-white",
    warning: "bg-warning text-white",
    error: "bg-error text-white",
    secondary: "bg-secondary text-white",
  }[tone];
  return (
    <div className={`${bg} border-[3px] border-black offset-shadow p-6`}>
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="font-mono text-[10px] font-bold uppercase tracking-widest opacity-80">
          {label}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

export function KV({ k, v, mono = false }: { k: string; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start gap-4 text-sm py-1">
      <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant/80 w-40 shrink-0 pt-1">
        {k}
      </div>
      <div className={`flex-1 ${mono ? "font-mono" : ""}`}>{v}</div>
    </div>
  );
}

export function Chip({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "error" | "info";
}) {
  const color = {
    neutral: "bg-white text-black",
    success: "bg-success text-white",
    warning: "bg-warning text-white",
    error: "bg-error text-white",
    info: "bg-primary-container text-black",
  }[tone];
  return (
    <span
      className={`inline-block font-mono text-[10px] font-black uppercase tracking-widest px-2 py-1 border-[3px] border-black ${color}`}
    >
      {children}
    </span>
  );
}

export function ScoreBar({
  score,
  label,
  hint,
}: {
  score: number | null | undefined;
  label: string;
  hint?: string;
}) {
  const pct = score == null ? 0 : Math.max(0, Math.min(100, score));
  const tone =
    score == null ? "bg-surface-container-high"
    : score >= 75 ? "bg-success"
    : score >= 50 ? "bg-primary-container"
    : "bg-error";
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <div className="font-mono text-[10px] uppercase tracking-widest">
          {label}
        </div>
        <div className="font-display text-xl font-black tabular-nums">
          {score != null ? score.toFixed(0) : "—"}
        </div>
      </div>
      <div className="h-2 w-full border-[2px] border-black bg-white">
        <div className={`h-full ${tone} transition-[width]`} style={{ width: `${pct}%` }} />
      </div>
      {hint && (
        <div className="mt-1 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant/70">
          {hint}
        </div>
      )}
    </div>
  );
}

export function Sar({
  amount,
  size = "base",
}: {
  amount: number | null | undefined;
  size?: "sm" | "base" | "lg" | "xl";
}) {
  const classes = {
    sm: "text-sm",
    base: "text-base",
    lg: "text-2xl font-black",
    xl: "font-display text-4xl font-black",
  }[size];
  if (amount == null) return <span className="text-on-surface-variant">—</span>;
  return (
    <span className={`inline-flex items-baseline gap-1 ${classes}`}>
      <RiyalSymbol className="h-[0.8em] w-[0.72em] translate-y-[0.05em]" />
      <span className="tabular-nums">{amount.toLocaleString("en-US")}</span>
    </span>
  );
}

export function RawJson({ data, label = "Raw JSON" }: { data: unknown; label?: string }) {
  return (
    <details className="bg-surface-container-low border-[3px] border-black p-3">
      <summary className="cursor-pointer list-none font-mono text-[10px] font-black uppercase tracking-widest flex items-center gap-2">
        <span>▸ {label}</span>
        <span className="text-on-surface-variant">(click to view)</span>
      </summary>
      <pre className="mt-3 font-mono text-[10px] overflow-auto max-h-80 whitespace-pre-wrap break-all">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  );
}

export function Metric({
  label,
  value,
  sub,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
}) {
  return (
    <div className="border-[3px] border-black p-4 bg-white">
      <div className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
        {label}
      </div>
      <div className="mt-1 font-display text-2xl font-black leading-tight">{value}</div>
      {sub && (
        <div className="mt-1 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
          {sub}
        </div>
      )}
    </div>
  );
}

/** Tabular key/value grid — use for feature/ratio blobs where each key is one
 *  cell. Renders `—` for null values, formats numbers, stringifies anything
 *  exotic. */
export function FeatureGrid({
  features,
  pickKeys,
  formatters,
}: {
  features: Record<string, unknown> | null | undefined;
  pickKeys?: string[];
  formatters?: Record<string, (v: unknown) => ReactNode>;
}) {
  if (!features) return null;
  const keys = pickKeys ?? Object.keys(features).filter((k) => {
    const v = features[k];
    return v == null || ["string", "number", "boolean"].includes(typeof v);
  });
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
      {keys.map((k) => {
        const v = features[k];
        const formatter = formatters?.[k];
        return (
          <div key={k} className="border-[3px] border-black bg-white px-3 py-2">
            <div className="font-mono text-[9px] uppercase tracking-widest text-on-surface-variant truncate">
              {k.replace(/_/g, " ")}
            </div>
            <div className="mt-1 font-mono text-sm font-bold truncate">
              {formatter ? formatter(v) : formatValue(v)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function formatValue(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") {
    if (Math.abs(v) >= 1000) return v.toLocaleString("en-US", { maximumFractionDigits: 2 });
    if (Number.isInteger(v)) return String(v);
    return v.toFixed(2);
  }
  if (typeof v === "string" || typeof v === "boolean") return String(v);
  return JSON.stringify(v).slice(0, 40);
}

export function formatPct(v: unknown): string {
  if (typeof v !== "number") return formatValue(v);
  return `${(v * 100).toFixed(1)}%`;
}

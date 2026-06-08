import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { RiyalSymbol } from "../components/RiyalSymbol";

const SLIDES: Array<{ id: string; label: string; render: () => ReactNode }> = [
  { id: "title",    label: "IMDAD",        render: () => <TitleSlide /> },
  { id: "team",     label: "Team",         render: () => <TeamSlide /> },
  { id: "problem",  label: "Ahmed",        render: () => <ProblemSlide /> },
  { id: "scale",    label: "× 132,383",    render: () => <ScaleSlide /> },
  { id: "gap",      label: "The Gap",      render: () => <GapSlide /> },
  { id: "model",    label: "Model",        render: () => <ModelSlide /> },
  { id: "engine",   label: "Decision",     render: () => <EngineSlide /> },
  { id: "stream",   label: "Stream",       render: () => <StreamSlide /> },
  { id: "ledger",   label: "Live Ledger",  render: () => <LedgerSlide /> },
  { id: "close",    label: "Close",        render: () => <CloseSlide /> },
];

export function Slides() {
  const isPrint =
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).has("all");

  return isPrint ? <PrintAll /> : <SlideShow />;
}

function SlideShow() {
  const [index, setIndex] = useState(0);
  const total = SLIDES.length;
  const slide = SLIDES[index];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " " || e.key === "PageDown") {
        e.preventDefault();
        setIndex((i) => Math.min(i + 1, total - 1));
      }
      if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        setIndex((i) => Math.max(i - 1, 0));
      }
      if (e.key === "Home") setIndex(0);
      if (e.key === "End") setIndex(total - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [total]);

  return (
    <div className="min-h-screen bg-black flex flex-col items-center justify-center p-6 gap-6 overflow-hidden">
      <div className="w-full max-w-[1280px] aspect-video bg-surface border-[3px] border-black offset-shadow-lg relative overflow-hidden">
        <SlideFrame index={index} total={total} label={slide.label}>
          {slide.render()}
        </SlideFrame>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => setIndex((i) => Math.max(i - 1, 0))}
          disabled={index === 0}
          className="bg-white border-[3px] border-black px-4 h-10 font-mono text-xs font-black uppercase tracking-widest offset-shadow hover-lift disabled:opacity-30 disabled:cursor-not-allowed"
        >
          ← Prev
        </button>
        <div className="flex gap-1.5">
          {SLIDES.map((s, i) => (
            <button
              key={s.id}
              onClick={() => setIndex(i)}
              aria-label={`Go to slide ${i + 1}: ${s.label}`}
              className={`w-3 h-3 border-2 border-white ${i === index ? "bg-primary-container" : "bg-transparent"}`}
            />
          ))}
        </div>
        <button
          onClick={() => setIndex((i) => Math.min(i + 1, total - 1))}
          disabled={index === total - 1}
          className="bg-primary-container border-[3px] border-black px-4 h-10 font-mono text-xs font-black uppercase tracking-widest offset-shadow hover-lift disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Next →
        </button>
        <Link
          to="/"
          className="ml-4 font-mono text-[10px] uppercase tracking-widest text-white/50 hover:text-[#FDC800]"
        >
          exit deck →
        </Link>
      </div>
    </div>
  );
}

function PrintAll() {
  return (
    <>
      <style>{`
        @page { size: 1280px 720px; margin: 0; }
        html, body { margin: 0; padding: 0; background: white; }
        #root { background: white; }
        .print-slide {
          width: 1280px;
          height: 720px;
          page-break-after: always;
          break-after: page;
          position: relative;
          overflow: hidden;
          background: var(--color-surface, #f5f5f3);
        }
        .print-slide:last-child { page-break-after: auto; break-after: auto; }
      `}</style>
      <div>
        {SLIDES.map((s, i) => (
          <div key={s.id} className="print-slide">
            <SlideFrame index={i} total={SLIDES.length} label={s.label}>
              {s.render()}
            </SlideFrame>
          </div>
        ))}
      </div>
    </>
  );
}

function SlideFrame({
  index,
  total,
  label,
  children,
}: {
  index: number;
  total: number;
  label: string;
  children: ReactNode;
}) {
  return (
    <>
      <div className="absolute top-5 left-6 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant z-20 flex items-center gap-2">
        <span className="w-2 h-2 bg-black" />
        IMDAD · Sub4.0 @ KFUPM · Streamathon 2026
      </div>
      <div className="absolute top-5 right-6 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant z-20">
        {String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")} · {label}
      </div>
      <div className="absolute inset-x-0 top-0 pointer-events-none h-10 border-b-[3px] border-black" />

      <div className="absolute left-0 right-0 top-10 bottom-[56px]">{children}</div>

      <LogoFooter />
    </>
  );
}

function LogoFooter() {
  return (
    <div className="absolute left-0 right-0 bottom-0 h-[56px] bg-black border-t-[3px] border-black z-10 flex items-center justify-between pl-6 pr-8 gap-6">
      <div className="font-mono text-[9px] uppercase tracking-widest text-white/40 shrink-0">
        Powered by
      </div>
      <div className="flex items-center gap-8 justify-end">
        <img src="/logos/01-stream.png" alt="Stream" className="h-6 object-contain" />
        <img src="/logos/02-replit.png" alt="Replit" className="h-6 object-contain" />
        <img src="/logos/03-kfupm.png" alt="KFUPM Student Affairs" className="h-8 object-contain" />
        <img src="/logos/04-computer-club.png" alt="KFUPM Computer Club" className="h-9 object-contain" />
      </div>
    </div>
  );
}

function Eyebrow({ text }: { text: string }) {
  return (
    <div className="font-mono text-sm font-bold uppercase tracking-[0.25em] text-on-surface-variant flex items-center gap-3">
      <span className="w-10 h-[3px] bg-black" />
      {text}
    </div>
  );
}

/* ─── 01 · TITLE ────────────────────────────────────────────────────────── */

function TitleSlide() {
  return (
    <div className="w-full h-full flex flex-col justify-center p-16 relative">
      <div className="font-mono text-sm uppercase tracking-[0.3em] text-on-surface-variant">
        Streamathon · Riyadh · 2026
      </div>

      <h1 className="mt-8 text-[220px] font-black leading-[0.82] tracking-tighter uppercase text-black">
        <span className="relative inline-block">
          IMDAD
          <span className="absolute bottom-4 left-0 w-full h-5 bg-[#FDC800] -z-10" />
        </span>
      </h1>

      <p className="mt-8 text-3xl font-medium text-on-surface-variant max-w-3xl leading-tight">
        Invoice-to-lease financing for the Kingdom&apos;s cafés.
      </p>

      <div className="mt-auto flex items-end justify-between">
        <div>
          <div className="font-mono text-xs uppercase tracking-[0.25em] text-on-surface-variant">
            Team
          </div>
          <div className="mt-2 text-2xl font-black uppercase tracking-tight">
            Sub4.0 · KFUPM
          </div>
        </div>
        <div className="text-right">
          <div className="font-mono text-xs uppercase tracking-[0.25em] text-on-surface-variant">
            Arabic: إمداد · supply
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── 02 · TEAM ─────────────────────────────────────────────────────────── */

function TeamSlide() {
  const members = [
    "Mohammed Moallem",
    "Abdullah Madon",
    "Abdulrazzak Ghazal",
    "Abdulaziz Elkarm",
    "Jamal Alajaji",
  ];
  return (
    <div className="w-full h-full p-16 flex flex-col">
      <Eyebrow text="The team" />
      <h2 className="mt-8 text-[96px] font-black tracking-tighter uppercase leading-[0.88]">
        Sub4.0<br />
        <span className="text-on-surface-variant">@ KFUPM</span>
      </h2>

      <div className="mt-12 grid grid-cols-5 gap-5 flex-grow">
        {members.map((m) => (
          <div key={m} className="bg-white border-[3px] border-black offset-shadow p-5 flex flex-col justify-between">
            <div className="w-10 h-10 bg-[#FDC800] border-[3px] border-black" />
            <div>
              <div className="font-black text-lg leading-tight tracking-tight">
                {m}
              </div>
              <div className="mt-2 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">
                Builder
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── 03 · PROBLEM / AHMED ─────────────────────────────────────────────── */

function ProblemSlide() {
  return (
    <div className="w-full h-full p-16 flex flex-col">
      <Eyebrow text="01 · The problem" />

      <h2 className="mt-8 text-[88px] font-black tracking-tighter uppercase leading-[0.86] text-black">
        Ahmed&apos;s café<br />
        needs one machine.<br />
        <span className="relative inline-block">
          His bank said no.
          <span className="absolute bottom-3 left-0 w-full h-4 bg-[#FDC800] -z-10" />
        </span>
      </h2>

      <div className="mt-auto grid grid-cols-2 gap-0 border-[3px] border-black offset-shadow-md">
        <div className="bg-white p-8">
          <div className="font-mono text-xs uppercase tracking-[0.25em] text-on-surface-variant mb-3">
            The banked
          </div>
          <div className="font-display text-[96px] font-black leading-none tracking-tighter">
            1 in 20
          </div>
          <div className="mt-3 text-lg text-on-surface-variant">
            cafés have a commercial bank relationship.
          </div>
        </div>
        <div className="bg-black p-8 text-white">
          <div className="font-mono text-xs uppercase tracking-[0.25em] text-white/50 mb-3">
            The unbanked
          </div>
          <div className="font-display text-[96px] font-black leading-none tracking-tighter text-[#FDC800]">
            19 in 20
          </div>
          <div className="mt-3 text-lg text-white/70">
            are on their own. No collateral. No history. No time.
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── 04 · SCALE · Ahmed × 132,383 ──────────────────────────────────────── */

function ScaleSlide() {
  return (
    <div className="w-full h-full p-16 flex flex-col justify-center">
      <Eyebrow text="02 · At scale" />

      <div className="mt-10 text-center">
        <div className="font-mono text-base uppercase tracking-[0.3em] text-on-surface-variant">
          Ahmed ×
        </div>
        <div className="mt-4 font-display text-[260px] font-black leading-none tracking-tighter text-black">
          <span className="relative inline-block">
            132,383
            <span className="absolute bottom-4 left-0 w-full h-5 bg-[#FDC800] -z-10" />
          </span>
        </div>
      </div>

      <p className="mt-10 text-3xl text-center font-medium max-w-4xl mx-auto leading-tight text-on-surface-variant">
        Every restaurant, café, and bakery in Saudi Arabia is an Ahmed.
      </p>
    </div>
  );
}

/* ─── 05 · GAP · 9.6% → 20% ─────────────────────────────────────────────── */

function GapSlide() {
  return (
    <div className="w-full h-full p-14 flex flex-col">
      <Eyebrow text="03 · The gap" />

      <h2 className="mt-6 text-[48px] font-black tracking-tighter uppercase leading-[0.92]">
        SME credit is <span className="bg-[#FDC800] px-2">half</span><br />
        of what Vision 2030 needs.
      </h2>

      <div className="mt-7 grid grid-cols-2 gap-0 border-[3px] border-black offset-shadow-md">
        <div className="bg-white p-8">
          <div className="font-mono text-xs uppercase tracking-[0.25em] text-on-surface-variant mb-3">
            Today
          </div>
          <div className="font-display text-[120px] font-black leading-none tracking-tighter">
            9.6<span className="text-[80px]">%</span>
          </div>
          <div className="mt-3 text-base text-on-surface-variant">
            SME share of bank credit.
          </div>
        </div>
        <div className="bg-[#FDC800] p-8">
          <div className="font-mono text-xs uppercase tracking-[0.25em] text-black/60 mb-3">
            Vision 2030 · target
          </div>
          <div className="font-display text-[120px] font-black leading-none tracking-tighter">
            20<span className="text-[80px]">%</span>
          </div>
          <div className="mt-3 text-base text-black/70">
            Mandated. Not optional.
          </div>
        </div>
      </div>

      <div className="mt-5 bg-white border-[3px] border-black offset-shadow p-4">
        <div className="relative h-6 border-[3px] border-black bg-surface-container">
          <div className="absolute inset-y-0 left-0 bg-[#FDC800]" style={{ width: `${(9.6 / 20) * 100}%` }} />
        </div>
        <div className="mt-2 flex justify-between font-mono text-[10px] uppercase tracking-widest font-black">
          <span>0%</span>
          <span>9.6% · today</span>
          <span>20% · Vision 2030</span>
        </div>
      </div>
    </div>
  );
}

/* ─── 06 · BUSINESS MODEL ───────────────────────────────────────────────── */

function ModelSlide() {
  return (
    <div className="w-full h-full p-12 flex flex-col">
      <Eyebrow text="04 · How IMDAD makes money" />
      <h2 className="mt-4 text-[42px] font-black tracking-tighter uppercase leading-[0.95]">
        We buy the item.<br />
        We <span className="bg-[#FDC800] px-2">lease it back</span> at a markup.
      </h2>

      <div className="mt-6 grid grid-cols-4 gap-0 border-[3px] border-black offset-shadow-md bg-white">
        {[
          { n: "01", t: "Merchant sends invoice", b: "Vendor quote · SAR 50,000." },
          { n: "02", t: "IMDAD pays the vendor", b: "We own the equipment. Not a loan." },
          { n: "03", t: "Merchant leases it back", b: "Fixed monthly installments." },
          { n: "04", t: "Merchant owns at payoff", b: "Total paid > cost. Spread = revenue." },
        ].map((s, i, arr) => (
          <div key={s.n} className={`p-5 flex flex-col ${i < arr.length - 1 ? "border-r-[3px] border-black" : ""}`}>
            <div className="font-mono text-4xl font-black leading-none">{s.n}</div>
            <div className="mt-4 font-black text-base leading-tight tracking-tight">
              {s.t}
            </div>
            <div className="mt-2 text-xs text-on-surface-variant leading-snug">{s.b}</div>
          </div>
        ))}
      </div>

      <div className="mt-4 bg-black border-[3px] border-black offset-shadow-lg p-5 text-white flex-grow flex flex-col justify-center">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-[#FDC800] mb-3">
          Example · 12-month lease
        </div>
        <div className="grid grid-cols-4 gap-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-white/50">Invoice cost</div>
            <div className="mt-1 font-display text-[28px] font-black flex items-baseline gap-1">
              <RiyalSymbol className="h-[0.65em] w-[0.6em] translate-y-[0.05em]" />
              <span>50,000</span>
            </div>
          </div>
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-white/50">Monthly × 12</div>
            <div className="mt-1 font-display text-[28px] font-black flex items-baseline gap-1">
              <RiyalSymbol className="h-[0.65em] w-[0.6em] translate-y-[0.05em]" />
              <span>4,791.67</span>
            </div>
          </div>
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-white/50">Total paid</div>
            <div className="mt-1 font-display text-[28px] font-black flex items-baseline gap-1">
              <RiyalSymbol className="h-[0.65em] w-[0.6em] translate-y-[0.05em]" />
              <span>57,500</span>
            </div>
          </div>
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#FDC800]">Our margin · 15%</div>
            <div className="mt-1 font-display text-[28px] font-black text-[#FDC800] flex items-baseline gap-1">
              <RiyalSymbol className="h-[0.65em] w-[0.6em] translate-y-[0.05em]" />
              <span>7,500</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── 07 · DECISION ENGINE ──────────────────────────────────────────────── */

function EngineSlide() {
  return (
    <div className="w-full h-full p-12 flex flex-col">
      <div className="flex items-end justify-between">
        <div>
          <Eyebrow text="05 · The decision engine" />
          <h2 className="mt-4 text-[44px] font-black tracking-tighter uppercase leading-[0.95]">
            Four data streams.<br />
            One decision in <span className="bg-[#FDC800] px-2">90 seconds</span>.
          </h2>
        </div>
        <p className="font-mono text-xs uppercase tracking-widest max-w-xs border-l-[3px] border-black pl-4 text-on-surface-variant">
          The machine is the collateral.<br />The merchant owns it at payoff.
        </p>
      </div>

      <div className="mt-6 grid grid-cols-[1fr_auto_1.1fr_auto_1fr] gap-3 items-stretch flex-grow">
        <div className="flex flex-col gap-2">
          <div className="font-mono text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-1">
            ▸ Merchant side
          </div>
          <InputNode icon="upload_file" title="Drag & Drop" body="Bank · POS · financial statement" />
          <InputNode icon="badge" title="SIMAH Login" body="Loan history · credit profile" />
          <InputNode icon="travel_explore" title="Maps Scraper" body="Review sentiment · public trust" />
          <InputNode icon="schedule" title="Duration" body="3 / 6 / 12 / 18 months" />
        </div>

        <FlowArrow />

        <div className="flex flex-col gap-2 items-stretch justify-center">
          <div className="font-mono text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-1">
            ▸ IMDAD decision
          </div>
          <GovernorNode title="Market Governor" body="KSA F&B health · risk envelope" />
          <FlowVertical />
          <div className="bg-black text-white border-[3px] border-black offset-shadow-lg p-4 flex flex-col">
            <div className="font-mono text-[10px] font-black uppercase tracking-widest text-[#FDC800] mb-1">
              Expert LLM
            </div>
            <div className="text-xl font-black uppercase tracking-tight leading-[1.05]">
              Approve · Deny<br />+ Threshold
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-white/40 mt-2">
              Rules-anchored · audit-traceable
            </div>
          </div>
          <FlowVertical />
          <GovernorNode title="Cashflow Governor" body="Portfolio vs. baseline · thresholds" />
        </div>

        <FlowArrow />

        <div className="flex flex-col gap-2">
          <div className="font-mono text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-1">
            ▸ Stream runs it
          </div>
          <div className="bg-[#FDC800] border-[3px] border-black offset-shadow flex-grow flex flex-col p-4">
            <div className="font-mono text-[10px] font-black uppercase tracking-widest text-black mb-3">
              3 API calls
            </div>
            <div className="space-y-1.5 font-mono text-[11px] text-black">
              <div><span className="font-black">POST</span> /consumers</div>
              <div><span className="font-black">POST</span> /payment-methods</div>
              <div><span className="font-black">POST</span> /subscriptions</div>
            </div>
            <div className="mt-auto pt-3 border-t-[2px] border-black/20">
              <div className="font-mono text-[10px] uppercase tracking-widest text-black/70">
                Then IMDAD goes silent.
              </div>
              <div className="mt-1 font-black text-xs leading-tight text-black">
                Stream bills · retries · receipts · closes.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function InputNode({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <div className="bg-white border-[3px] border-black offset-shadow px-3 py-2 flex items-start gap-2 flex-grow">
      <span className="material-symbols-outlined text-lg shrink-0 mt-0.5">{icon}</span>
      <div className="min-w-0">
        <div className="font-mono text-[10px] font-black uppercase tracking-widest leading-tight">
          {title}
        </div>
        <div className="text-[11px] text-on-surface-variant leading-tight mt-0.5">{body}</div>
      </div>
    </div>
  );
}

function GovernorNode({ title, body }: { title: string; body: string }) {
  return (
    <div className="bg-white border-[3px] border-dashed border-black px-3 py-2">
      <div className="font-mono text-[10px] font-black uppercase tracking-widest leading-tight">
        ⚙ {title}
      </div>
      <div className="text-[11px] text-on-surface-variant leading-tight mt-0.5">{body}</div>
    </div>
  );
}

function FlowArrow() {
  return (
    <div className="flex items-center justify-center">
      <span className="material-symbols-outlined text-3xl">chevron_right</span>
    </div>
  );
}

function FlowVertical() {
  return (
    <div className="flex items-center justify-center h-3">
      <div className="w-[3px] h-full bg-black" />
    </div>
  );
}

/* ─── 08 · STREAM INTEGRATION ──────────────────────────────────────────── */

function StreamSlide() {
  return (
    <div className="w-full h-full p-12 flex flex-col">
      <div className="flex items-end justify-between">
        <div>
          <Eyebrow text="06 · The payments layer" />
          <h2 className="mt-4 text-[40px] font-black tracking-tighter uppercase leading-[0.95]">
            Three calls.{" "}
            <span className="bg-[#FDC800] px-2">Then silence.</span><br />
            Stream runs every riyal after approval.
          </h2>
        </div>
        <p className="font-mono text-xs uppercase tracking-widest max-w-xs border-l-[3px] border-black pl-4 text-on-surface-variant">
          We built the underwriter.<br />Stream built the rest.
        </p>
      </div>

      <div className="mt-5 bg-black border-[3px] border-black offset-shadow-lg p-5 font-mono text-xs text-white">
        <div className="text-[#FDC800] mb-3 font-black uppercase tracking-widest text-[10px]">
          /* 3 API calls */
        </div>
        <div className="space-y-2">
          <div className="flex items-baseline gap-4">
            <span className="text-[#FDC800] font-black w-52 shrink-0">POST /consumers</span>
            <span className="text-white/80 flex-1">→ Ahmed in Stream · KYC stored · card vaulted</span>
            <span className="text-white/40 text-[10px] shrink-0">[once]</span>
          </div>
          <div className="flex items-baseline gap-4">
            <span className="text-[#FDC800] font-black w-52 shrink-0">POST /payment-methods</span>
            <span className="text-white/80 flex-1">→ Method saved · we never touch card data</span>
            <span className="text-white/40 text-[10px] shrink-0">[PCI handled]</span>
          </div>
          <div className="flex items-baseline gap-4">
            <span className="text-[#FDC800] font-black w-52 shrink-0">POST /subscriptions</span>
            <span className="text-white/80 flex-1">→ SAR X × N cycles · auto-collected</span>
            <span className="text-white/40 text-[10px] shrink-0">[contract]</span>
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-4 gap-0 border-[3px] border-black offset-shadow-md bg-white flex-grow">
        {[
          { t: "Auto-billing",          b: "Charges each cycle. Reminders fire for upcoming, failed, late." },
          { t: "Installments engine",   b: "Native Stream plan. N equal cycles. Auto-collected on due date." },
          { t: "Card failure recovery", b: "Decline → retry → Arabic update link → re-attempt." },
          { t: "ZATCA invoices",        b: "Every settled cycle. VAT-accurate, branded, Arabic." },
        ].map((it, i, arr) => (
          <div
            key={it.t}
            className={`p-4 flex flex-col ${i < arr.length - 1 ? "border-r-[3px] border-black" : ""}`}
          >
            <div className="font-mono text-[10px] font-black uppercase tracking-widest text-black">
              ▸ {it.t}
            </div>
            <div className="mt-2 text-[13px] text-on-surface-variant leading-snug">{it.b}</div>
          </div>
        ))}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-0 border-[3px] border-black">
        <div className="bg-white border-r-[3px] border-black p-3 flex items-center gap-3">
          <div className="font-mono text-[10px] font-black uppercase tracking-widest shrink-0">IMDAD</div>
          <div className="text-xs text-on-surface-variant">Decide if Ahmed deserves the machine.</div>
        </div>
        <div className="bg-[#FDC800] p-3 flex items-center gap-3">
          <div className="font-mono text-[10px] font-black uppercase tracking-widest shrink-0">Stream</div>
          <div className="text-xs text-black/80">Move every riyal after he does.</div>
        </div>
      </div>
    </div>
  );
}

/* ─── 09 · LIVE LEDGER ─────────────────────────────────────────────────── */

function LedgerSlide() {
  return (
    <div className="w-full h-full grid grid-cols-12 gap-8 p-14">
      <div className="col-span-5 flex flex-col">
        <Eyebrow text="07 · Running today" />
        <h2 className="mt-6 text-[64px] font-black leading-[0.88] tracking-tighter uppercase">
          Not a mockup.<br />
          <span className="bg-[#FDC800] px-2 inline-block">A ledger.</span>
        </h2>
        <p className="mt-6 text-on-surface-variant text-xl max-w-md leading-snug">
          Backend runs end-to-end. Every decision is a row. Every installment a receipt.
        </p>

        <div className="mt-auto space-y-3">
          <Row k="Underwriting" v="FastAPI · LLM + rules" />
          <Row k="Data" v="Supabase · Mumbai · RLS" />
          <Row k="Payments" v="Stream.sa auto-debit" />
        </div>
      </div>
      <div className="col-span-7">
        <LedgerTerminal />
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="border-b-[3px] border-black pb-2 flex items-center justify-between">
      <span className="font-mono text-sm uppercase tracking-widest font-black">{k}</span>
      <span className="text-on-surface-variant text-base">{v}</span>
    </div>
  );
}

function LedgerTerminal() {
  return (
    <div className="bg-black border-[3px] border-black offset-shadow-lg w-full h-full flex flex-col overflow-hidden">
      <div className="bg-secondary border-b-[3px] border-black p-3 flex items-center justify-between">
        <div className="flex gap-2">
          <div className="w-3 h-3 bg-white border border-black" />
          <div className="w-3 h-3 bg-white border border-black opacity-50" />
          <div className="w-3 h-3 bg-white border border-black opacity-20" />
        </div>
        <div className="font-mono text-[10px] text-white font-bold tracking-widest">
          AHMED.COFFEE · ACTIVE_LEASE.LEDGER
        </div>
      </div>
      <div className="p-6 font-mono flex-grow flex flex-col scanline">
        <div className="flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-green-400 animate-pulse" />
          <span className="text-green-400 text-[10px] font-black uppercase tracking-widest">
            Approved · 87s
          </span>
        </div>
        <div className="text-white/40 text-[10px] uppercase tracking-widest mb-1">
          Principal financed
        </div>
        <div className="text-[#FDC800] text-[56px] font-black leading-none mb-2 flex items-baseline gap-3">
          <RiyalSymbol className="h-[0.8em] w-[0.72em] translate-y-[0.05em]" />
          <span>50,000</span>
        </div>
        <div className="text-white/60 text-[10px] uppercase tracking-widest mb-4">
          12 mo · fixed · auto-debit · asset: espresso machine
        </div>
        <div className="border-t-[2px] border-white/20 mb-3" />
        <div className="text-white/40 text-[10px] uppercase tracking-widest mb-2">
          Repayment ledger
        </div>
        <div className="space-y-[6px] flex-grow text-sm">
          <LedgerRow n="01" d="MAY 01" a="4,791.67" s="paid" />
          <LedgerRow n="02" d="JUN 01" a="4,791.67" s="due" />
          <LedgerRow n="03" d="JUL 01" a="4,791.67" s="queued" />
          <LedgerRow n="04" d="AUG 01" a="4,791.67" s="queued" />
          <LedgerRow n="05" d="SEP 01" a="4,791.67" s="queued" />
          <div className="text-white/30 pt-[2px] text-xs">· · · 7 more</div>
        </div>
      </div>
    </div>
  );
}

function LedgerRow({ n, d, a, s }: { n: string; d: string; a: string; s: "paid" | "due" | "queued" }) {
  const chip =
    s === "paid"   ? <span className="text-green-400">✓ PAID</span>
    : s === "due"  ? <span className="text-[#FDC800]">● DUE 14D</span>
                   : <span className="text-white/35">— QUEUED</span>;
  return (
    <div className="flex items-center justify-between text-white">
      <span className="text-white/40 w-8">[{n}]</span>
      <span className="text-white/65 flex-1">{d}</span>
      <span className="text-white w-24 text-right tabular-nums">{a}</span>
      <span className="w-28 text-right text-[10px] font-black uppercase tracking-widest">{chip}</span>
    </div>
  );
}

/* ─── 08 · CLOSE ────────────────────────────────────────────────────────── */

function CloseSlide() {
  return (
    <div className="w-full h-full p-16 flex flex-col justify-center relative">
      <Eyebrow text="08 · Close" />

      <h2 className="mt-8 text-[120px] font-black tracking-tighter uppercase leading-[0.85]">
        9.6% → <span className="bg-black text-[#FDC800] px-4">20%</span>
      </h2>

      <p className="mt-8 text-3xl font-medium leading-tight max-w-3xl text-on-surface-variant">
        The bridge from today to Vision 2030.<br />
        <span className="text-black font-black">One invoice at a time.</span>
      </p>

      <div className="mt-auto flex items-end justify-between">
        <div>
          <div className="font-display text-6xl font-black tracking-tighter uppercase leading-none">
            IMDAD
          </div>
          <div className="mt-3 font-mono text-xs uppercase tracking-[0.25em] text-on-surface-variant">
            Sub4.0 @ KFUPM · Streamathon 2026
          </div>
        </div>
        <div className="bg-[#FDC800] border-[3px] border-black offset-shadow-lg px-10 h-20 flex items-center text-3xl font-black uppercase tracking-tight">
          Let&apos;s ship it →
        </div>
      </div>
    </div>
  );
}

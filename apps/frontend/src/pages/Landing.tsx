import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { RiyalSymbol } from "../components/RiyalSymbol";

export function Landing() {
  return (
    <div className="bg-surface text-on-surface min-h-screen">
      <TopNav />
      <Hero />
      <HowItWorks />
      <TransparentByDesign />
      <CtaBanner />
      <Footer />
    </div>
  );
}

function TopNav() {
  return (
    <nav className="bg-[#FBFBF9] border-b-[3px] border-black flex justify-between items-center w-full px-6 h-16 fixed top-0 left-0 right-0 z-50">
      <Link to="/" className="text-2xl font-black tracking-tighter text-black uppercase">
        LeaseFlow
      </Link>
      <div className="hidden md:flex gap-8 items-center font-mono text-xs uppercase tracking-widest">
        <a className="text-on-surface-variant hover:bg-primary-container hover:text-black transition-colors px-2 py-1" href="#protocol">Protocol</a>
        <a className="text-on-surface-variant hover:bg-primary-container hover:text-black transition-colors px-2 py-1" href="#terms">Terms</a>
        <Link className="text-on-surface-variant hover:bg-primary-container hover:text-black transition-colors px-2 py-1" to="/login">Login</Link>
      </div>
      <div className="flex items-center gap-4">
        <Link
          to="/signup"
          className="bg-primary-container text-black font-black border-[3px] border-black px-4 h-10 flex items-center offset-shadow-sm hover-lift uppercase text-sm"
        >
          New Application
        </Link>
      </div>
    </nav>
  );
}

function Hero() {
  return (
    <main className="pt-32 pb-20 px-6 max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
      <div className="lg:col-span-7">
        <div className="font-mono text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-4 flex items-center gap-2">
          <span className="w-8 h-[3px] bg-black"></span>
          Institutional Grade Capital
        </div>
        <h1 className="text-6xl md:text-8xl font-black leading-none tracking-tighter text-black mb-8">
          Financing that doesn&apos;t make you{" "}
          <span className="relative inline-block">
            wait.
            <span className="absolute bottom-2 left-0 w-full h-[6px] bg-[#FDC800] -z-10"></span>
          </span>
        </h1>
        <p className="text-xl text-on-surface-variant max-w-xl mb-10 leading-relaxed font-medium">
          The Architectural Ledger for merchant growth. Secure up to{" "}
          <span className="inline-flex items-baseline gap-1.5 font-black text-on-surface whitespace-nowrap">
            <RiyalSymbol className="h-[0.8em] w-[0.72em] translate-y-[0.05em]" />
            250,000
          </span>{" "}
          in under 90 seconds using our automated underwriting infrastructure.
        </p>
        <Link
          to="/signup"
          className="inline-flex items-center gap-4 bg-primary-container text-black font-black border-[3px] border-black px-8 h-12 offset-shadow hover-lift transition-all group uppercase"
        >
          Apply now
          <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform">arrow_forward</span>
        </Link>
      </div>

      <div className="lg:col-span-5 relative">
        <TerminalWindow />
        <div className="absolute -bottom-6 -right-6 w-24 h-24 border-[3px] border-black bg-[#FDC800] -z-20"></div>
      </div>
    </main>
  );
}

function TerminalWindow() {
  return (
    <div className="bg-black border-[3px] border-black offset-shadow w-full aspect-square md:aspect-video lg:aspect-square flex flex-col overflow-hidden">
      <div className="bg-secondary border-b-[3px] border-black p-3 flex items-center justify-between">
        <div className="flex gap-2">
          <div className="w-3 h-3 bg-white border border-black" />
          <div className="w-3 h-3 bg-white border border-black opacity-50" />
          <div className="w-3 h-3 bg-white border border-black opacity-20" />
        </div>
        <div className="font-mono text-[10px] text-white font-bold tracking-widest">
          ACTIVE_LEASE.LEDGER
        </div>
      </div>
      <div className="p-6 font-mono flex-grow flex flex-col relative overflow-hidden scanline">
        <div className="flex items-center gap-2 mb-4">
          <span className="w-2 h-2 bg-green-400 animate-pulse" />
          <span className="text-green-400 text-[10px] font-black uppercase tracking-widest">
            Decision · Approved in 87s
          </span>
        </div>

        <div className="text-white/40 text-[10px] uppercase tracking-widest mb-1">
          Principal financed
        </div>
        <div className="text-[#FDC800] text-4xl md:text-5xl font-black leading-none mb-2 flex items-baseline gap-2">
          <RiyalSymbol className="h-[0.8em] w-[0.72em] translate-y-[0.05em]" />
          <span>48,000</span>
        </div>
        <div className="text-white/60 text-[10px] uppercase tracking-widest mb-5">
          12 mo · fixed · auto-debit
        </div>

        <div className="border-t-[2px] border-white/20 mb-3" />

        <div className="text-white/40 text-[10px] uppercase tracking-widest mb-2">
          Repayment ledger
        </div>
        <div className="space-y-[6px] flex-grow">
          <LedgerRow n="01" date="MAY 01" amount="4,791.67" status="paid" />
          <LedgerRow n="02" date="JUN 01" amount="4,791.67" status="due" />
          <LedgerRow n="03" date="JUL 01" amount="4,791.67" status="queued" />
          <LedgerRow n="04" date="AUG 01" amount="4,791.67" status="queued" />
          <LedgerRow n="05" date="SEP 01" amount="4,791.67" status="queued" />
          <div className="text-white/30 text-xs pt-[2px]">· · · 7 more</div>
        </div>

        <div className="mt-3 inline-block bg-green-500 text-black px-2 py-1 font-black text-[10px] animate-pulse self-start uppercase tracking-widest">
          &gt; Funds disbursed
        </div>
      </div>
    </div>
  );
}

function LedgerRow({
  n,
  date,
  amount,
  status,
}: {
  n: string;
  date: string;
  amount: string;
  status: "paid" | "due" | "queued";
}) {
  const chip =
    status === "paid" ? (
      <span className="text-green-400">✓ PAID</span>
    ) : status === "due" ? (
      <span className="text-[#FDC800]">● DUE 14D</span>
    ) : (
      <span className="text-white/35">— QUEUED</span>
    );
  return (
    <div className="flex items-center justify-between text-xs text-white">
      <span className="text-white/40 w-8">[{n}]</span>
      <span className="text-white/65 flex-1">{date}</span>
      <span className="text-white w-24 text-right tabular-nums">SAR {amount}</span>
      <span className="w-24 text-right text-[10px] font-black uppercase tracking-widest">
        {chip}
      </span>
    </div>
  );
}

function HowItWorks() {
  const steps: Array<{ n: string; title: ReactNode; body: string; icon: string }> = [
    { n: "01", title: "Upload docs", body: "Connect your ERP or upload transaction statements. We ingest the raw data immediately.", icon: "description" },
    { n: "02", title: "We read them", body: "Our proprietary ledger engine parses your performance indicators in real-time.", icon: "terminal" },
    {
      n: "03",
      title: (
        <span className="inline-flex items-baseline gap-3">
          <span>You get</span>
          <RiyalSymbol className="h-[0.85em] w-[0.75em] translate-y-[0.05em]" />
        </span>
      ),
      body: "Funds are dispatched to your business account via instant architectural wire.",
      icon: "payments",
    },
  ];

  return (
    <section id="protocol" className="bg-surface-container-low border-y-[3px] border-black py-24 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-end mb-16 gap-6">
          <div>
            <div className="font-mono text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-4 flex items-center gap-2">
              <span className="w-8 h-[3px] bg-black"></span>
              The Protocol
            </div>
            <h2 className="text-5xl font-black tracking-tighter uppercase">How it works</h2>
          </div>
          <p className="font-mono text-sm max-w-xs border-l-[3px] border-black pl-4 uppercase">
            Our system eliminates the subjectivity of traditional banking through raw data analysis.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0 border-[3px] border-black">
          {steps.map((s, i) => (
            <div
              key={s.n}
              className={`p-10 bg-white hover:bg-[#FDC800] transition-colors group ${
                i < steps.length - 1 ? "border-b-[3px] md:border-b-0 md:border-r-[3px] border-black" : ""
              }`}
            >
              <div className="font-mono text-5xl font-black mb-8 group-hover:translate-x-2 transition-transform">{s.n}</div>
              <h3 className="text-2xl font-black uppercase mb-4 min-h-[2rem]">{s.title}</h3>
              <p className="text-on-surface-variant font-medium leading-relaxed">{s.body}</p>
              <div className="mt-8 flex gap-2">
                <span className="material-symbols-outlined font-black">{s.icon}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function TransparentByDesign() {
  const items = [
    { k: "FIXED_REPAYMENT", v: "No variable interest rates or hidden floating fees. What you see is what you pay back, calculated to the halala." },
    { k: "UNYIELDING_SECURITY", v: "Every byte of data is encrypted with enterprise-grade AES-256 infrastructure, hosted locally within the Kingdom." },
    { k: "MERCHANT_CENTRIC", v: "Built by founders for founders. We understand that cash flow is the oxygen of your business machine." },
  ];

  return (
    <section id="terms" className="py-24 px-6 max-w-7xl mx-auto">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
        <div>
          <div className="w-full aspect-[4/3] border-[3px] border-black offset-shadow mb-8 bg-black relative overflow-hidden">
            <div className="absolute inset-0 grid grid-cols-8 grid-rows-8">
              {Array.from({ length: 64 }).map((_, i) => (
                <div key={i} className="border border-white/5" />
              ))}
            </div>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-32 h-32 border-[3px] border-[#FDC800] rotate-45"></div>
            </div>
          </div>
          <div className="bg-black text-white p-6 font-mono text-sm flex justify-between items-center">
            <span>SYSTEM_ASSET_082</span>
            <span className="text-[#FDC800]">VERIFIED_SECURE</span>
          </div>
        </div>
        <div>
          <h2 className="text-4xl font-black tracking-tighter uppercase mb-8">Transparent by Design</h2>
          <div className="space-y-8">
            {items.map((it, i) => (
              <div key={it.k} className={i < items.length - 1 ? "border-b-[3px] border-black pb-8" : "pb-8"}>
                <h4 className="font-mono font-bold text-lg mb-2">{it.k}</h4>
                <p className="text-on-surface-variant">{it.v}</p>
              </div>
            ))}
          </div>
          <Link
            to="/signup"
            className="block w-full text-center bg-secondary text-white font-black border-[3px] border-black h-12 leading-[3rem] offset-shadow hover-lift mt-4 uppercase"
          >
            Start an application
          </Link>
        </div>
      </div>
    </section>
  );
}

function CtaBanner() {
  return (
    <section className="mb-24 px-6 max-w-7xl mx-auto">
      <div className="bg-[#FDC800] border-[3px] border-black p-12 flex flex-col md:flex-row items-center justify-between gap-12 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-32 h-32 border-r-[3px] border-b-[3px] border-black opacity-10"></div>
        <div className="absolute bottom-0 right-0 w-64 h-64 border-l-[3px] border-t-[3px] border-black opacity-10"></div>
        <div className="relative z-10 text-center md:text-left">
          <h2 className="text-5xl font-black tracking-tighter uppercase mb-4 leading-none">Ready to scale?</h2>
          <p className="font-mono font-bold text-black opacity-70">EXECUTE THE APPLICATION PROTOCOL TODAY.</p>
        </div>
        <div className="relative z-10">
          <Link
            to="/signup"
            className="inline-flex items-center bg-black text-[#FDC800] font-black border-[3px] border-black px-12 h-16 text-xl offset-shadow hover-lift uppercase"
          >
            Apply now &rarr;
          </Link>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="bg-black text-white py-16 px-6">
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-12">
        <div className="col-span-1 md:col-span-2">
          <div className="text-3xl font-black tracking-tighter uppercase text-[#FDC800] mb-6">LeaseFlow</div>
          <p className="font-mono text-sm opacity-50 max-w-xs mb-8">
            THE ARCHITECTURAL LEDGER FOR MERCHANT FINANCING. BUILT FOR SPEED. BUILT FOR SCALE. BUILT FOR GROWTH.
          </p>
        </div>
        <div>
          <h5 className="font-mono font-black uppercase mb-6 text-[#FDC800]">System</h5>
          <ul className="space-y-4 font-mono text-sm opacity-70">
            <li><Link className="hover:opacity-100" to="/login">Dashboard</Link></li>
            <li><a className="hover:opacity-100" href="#protocol">Protocol</a></li>
            <li><a className="hover:opacity-100" href="#terms">Terms</a></li>
          </ul>
        </div>
        <div>
          <h5 className="font-mono font-black uppercase mb-6 text-[#FDC800]">Support</h5>
          <ul className="space-y-4 font-mono text-sm opacity-70">
            <li><a className="hover:opacity-100" href="mailto:support@leaseflow.sa">Contact</a></li>
            <li><a className="hover:opacity-100" href="#">Privacy</a></li>
          </ul>
        </div>
      </div>
      <div className="max-w-7xl mx-auto mt-16 pt-8 border-t border-white/10 flex flex-col md:flex-row justify-between items-center gap-4">
        <div className="font-mono text-[10px] opacity-30">© 2026 LEASEFLOW_INFRASTRUCTURE. ALL RIGHTS RESERVED.</div>
        <div className="font-mono text-[10px] opacity-30">CONNECTED_TO: RIYADH_REGION_NODE_01</div>
      </div>
    </footer>
  );
}

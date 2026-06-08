import type { ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { useAuth } from "../hooks/useAuth";

type Props = {
  children: ReactNode;
  activeTab?: "pipeline" | "risk" | "segments";
};

const TABS: Array<{ key: NonNullable<Props["activeTab"]>; label: string; to: string }> = [
  { key: "pipeline", label: "Pipeline", to: "/admin" },
  { key: "risk",     label: "Risk",     to: "/admin/risk" },
  { key: "segments", label: "Segments", to: "/admin/segments" },
];

export function AdminShell({ children, activeTab }: Props) {
  const { profile } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate("/", { replace: true });
  };

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <header className="sticky top-0 z-40 bg-black text-white border-b-[3px] border-black h-16 flex items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <Link to="/admin" className="text-2xl font-black tracking-tighter uppercase text-[#FDC800]">
            LeaseFlow<span className="text-white">/admin</span>
          </Link>
          <nav className="hidden md:flex items-center gap-6 h-full">
            {TABS.map((t) => (
              <NavLink
                key={t.key}
                to={t.to}
                className={() => {
                  const isActive = activeTab === t.key;
                  return `font-mono text-xs uppercase tracking-widest px-2 py-1 transition-colors ${
                    isActive
                      ? "text-[#FDC800] border-b-[3px] border-[#FDC800] font-bold"
                      : "text-white/70 hover:bg-[#FDC800] hover:text-black"
                  }`;
                }}
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-4 font-mono text-xs uppercase tracking-widest">
          <span className="hidden sm:inline">{profile?.display_name ?? "Admin"}</span>
          <button
            onClick={handleLogout}
            className="border-[3px] border-white px-3 py-1 hover:bg-[#FDC800] hover:text-black hover:border-[#FDC800] transition-colors"
          >
            Logout
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-10">{children}</main>
    </div>
  );
}

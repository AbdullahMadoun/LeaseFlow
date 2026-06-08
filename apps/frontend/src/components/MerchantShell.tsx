import type { ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { useAuth } from "../hooks/useAuth";

type Props = {
  children: ReactNode;
  activeTab?: "dashboard" | "apply" | "payments" | "profile";
};

const TABS: Array<{ key: NonNullable<Props["activeTab"]>; label: string; to: string }> = [
  { key: "dashboard", label: "Dashboard", to: "/merchant/dashboard" },
  { key: "apply",     label: "New Lease", to: "/merchant/new-loan" },
  { key: "payments",  label: "Payments",  to: "/merchant/payments" },
  { key: "profile",   label: "Profile",   to: "/merchant/profile" },
];

export function MerchantShell({ children, activeTab }: Props) {
  const { profile } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate("/", { replace: true });
  };

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <header className="sticky top-0 z-40 bg-[#FBFBF9] border-b-[3px] border-black h-16 flex items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <Link to="/merchant/dashboard" className="text-2xl font-black tracking-tighter text-black uppercase">
            LeaseFlow
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
                      ? "text-black border-b-[3px] border-[#FDC800] font-bold"
                      : "text-on-surface-variant hover:bg-[#FDC800] hover:text-black"
                  }`;
                }}
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-4 font-mono text-xs uppercase tracking-widest">
          <span className="hidden sm:inline text-on-surface-variant">
            {profile?.display_name ?? "Merchant"}
          </span>
          <button
            onClick={handleLogout}
            className="border-[3px] border-black px-3 py-1 hover:bg-black hover:text-white transition-colors"
          >
            Logout
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10">{children}</main>
    </div>
  );
}

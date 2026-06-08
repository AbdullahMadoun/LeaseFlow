import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { AuthShell } from "../components/AuthShell";
import { supabase } from "../lib/supabase";
import { homePathFor } from "../hooks/useAuth";

export function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) {
      toast.error(error.message);
      return;
    }
    const { data: profile } = await supabase
      .from("profiles")
      .select("role")
      .eq("id", data.user.id)
      .maybeSingle();
    const from = (location.state as { from?: string } | null)?.from;
    navigate(from ?? homePathFor(profile?.role as "merchant" | "admin" | undefined), { replace: true });
  };

  return (
    <AuthShell terminal="~/login.sh" label="WELCOME BACK">
      <form onSubmit={handleSubmit} className="space-y-8" noValidate>
        <Field label="User Identity / Email">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="OPERATOR@LEASEFLOW.ARC"
            required
            autoComplete="email"
            className="w-full border-[3px] border-black bg-white p-4 font-mono text-sm uppercase placeholder:text-gray-300 focus:outline-none focus:bg-surface-container-low"
          />
        </Field>
        <Field label="Access Key / Password">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••••••"
            required
            autoComplete="current-password"
            className="w-full border-[3px] border-black bg-white p-4 font-mono text-sm focus:outline-none focus:bg-surface-container-low"
          />
        </Field>
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-primary-container text-black border-[3px] border-black py-5 px-6 font-mono font-black text-lg offset-shadow hover-lift flex items-center justify-center gap-3 uppercase disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span>{loading ? "VERIFYING…" : "LOG IN"}</span>
          {!loading && <span className="material-symbols-outlined font-black">arrow_forward</span>}
        </button>
      </form>
      <div className="mt-10 pt-8 border-t-[3px] border-black border-dashed flex flex-col sm:flex-row items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => toast.info("Password reset flow coming soon")}
          className="font-mono text-xs font-bold text-black hover:bg-black hover:text-white px-2 py-1 transition-colors uppercase"
        >
          Forgot access key?
        </button>
        <Link
          to="/signup"
          className="font-mono text-xs font-bold text-secondary flex items-center gap-2 group uppercase"
        >
          <span>No account? Sign up</span>
          <span className="material-symbols-outlined text-sm group-hover:translate-x-1 transition-transform">east</span>
        </Link>
      </div>
    </AuthShell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="relative">
      <label className="absolute -top-3 left-4 bg-surface px-2 font-mono text-[10px] font-bold text-black z-10 uppercase">
        {label}
      </label>
      {children}
    </div>
  );
}

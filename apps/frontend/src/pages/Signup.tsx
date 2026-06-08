import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { AuthShell } from "../components/AuthShell";
import { supabase } from "../lib/supabase";

export function Signup() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      toast.error("Access key must be at least 8 characters");
      return;
    }
    setLoading(true);
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { display_name: displayName || email.split("@")[0] } },
    });
    setLoading(false);
    if (error) {
      toast.error(error.message);
      return;
    }
    toast.success("Account created — welcome aboard");
    navigate("/merchant/dashboard", { replace: true });
  };

  return (
    <AuthShell terminal="~/signup.sh" label="NEW OPERATOR">
      <form onSubmit={handleSubmit} className="space-y-8" noValidate>
        <Field label="Business / Display Name">
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="ACME RESTAURANTS LLC"
            autoComplete="organization"
            className="w-full border-[3px] border-black bg-white p-4 font-mono text-sm uppercase placeholder:text-gray-300 focus:outline-none focus:bg-surface-container-low"
          />
        </Field>
        <Field label="Operator Email">
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
        <Field label="Access Key / Password (min 8)">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••••••"
            required
            autoComplete="new-password"
            minLength={8}
            className="w-full border-[3px] border-black bg-white p-4 font-mono text-sm focus:outline-none focus:bg-surface-container-low"
          />
        </Field>
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-primary-container text-black border-[3px] border-black py-5 px-6 font-mono font-black text-lg offset-shadow hover-lift flex items-center justify-center gap-3 uppercase disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span>{loading ? "CREATING…" : "CREATE ACCOUNT"}</span>
          {!loading && <span className="material-symbols-outlined font-black">arrow_forward</span>}
        </button>
      </form>
      <div className="mt-10 pt-8 border-t-[3px] border-black border-dashed flex justify-center">
        <Link
          to="/login"
          className="font-mono text-xs font-bold text-secondary flex items-center gap-2 group uppercase"
        >
          <span>Already have an account? Log in</span>
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

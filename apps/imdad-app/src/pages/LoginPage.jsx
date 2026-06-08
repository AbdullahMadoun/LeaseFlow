import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import TopNav from "../components/TopNav";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");

  function onSubmit(e) {
    e.preventDefault();
    const result = login(form);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    navigate(result.user.role === "admin" ? "/admin/dashboard" : "/dashboard");
  }

  return (
    <div>
      <TopNav title="Login" />
      <main className="auth-wrap">
        <section className="auth-form">
          <h1>Login</h1>
          <p>Access customer or admin workspace.</p>
          <form onSubmit={onSubmit}>
            <label>Email</label>
            <input type="email" required value={form.email} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} />
            <label>Password</label>
            <input type="password" required value={form.password} onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))} />
            {error && <p className="error-msg">{error}</p>}
            <button type="submit" className="btn primary">Sign In</button>
          </form>
          <p className="muted">No account? <Link to="/signup">Create one</Link></p>
          <p className="muted">Demo Admin: admin@imdad.sa / Admin@123</p>
          <p className="muted">Demo Customer: user@imdad.sa / User@123</p>
        </section>
        <section className="auth-art" aria-hidden="true">
          <h2>Fixed-Term Invoice Financing</h2>
        </section>
      </main>
    </div>
  );
}

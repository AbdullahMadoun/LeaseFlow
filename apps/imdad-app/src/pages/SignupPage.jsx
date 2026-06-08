import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import TopNav from "../components/TopNav";
import { useAuth } from "../context/AuthContext";

export default function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");

  function onSubmit(e) {
    e.preventDefault();
    const result = signup(form);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    navigate("/profile");
  }

  return (
    <div>
      <TopNav title="Signup" />
      <main className="auth-wrap">
        <section className="auth-form">
          <h1>Create Customer Account</h1>
          <p>Onboarding for cafes and restaurants.</p>
          <form onSubmit={onSubmit}>
            <label>Full Name</label>
            <input required value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} />
            <label>Email</label>
            <input type="email" required value={form.email} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} />
            <label>Password</label>
            <input type="password" required minLength={6} value={form.password} onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))} />
            {error && <p className="error-msg">{error}</p>}
            <button type="submit" className="btn primary">Create Account</button>
          </form>
          <p className="muted">Already registered? <Link to="/login">Login</Link></p>
        </section>
        <section className="auth-art" aria-hidden="true">
          <h2>Customer Onboarding</h2>
        </section>
      </main>
    </div>
  );
}

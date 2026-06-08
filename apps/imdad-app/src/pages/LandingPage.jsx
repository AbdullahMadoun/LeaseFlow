import { Link } from "react-router-dom";
import TopNav from "../components/TopNav";

export default function LandingPage() {
  return (
    <div>
      <TopNav title="Invoice Financing" />
      <main className="page public">
        <div className="landing-wrap">
          <section className="landing-hero">
            <div>
              <p className="eyebrow">Built For Cafes & Restaurants</p>
              <h1>Imdad helps hospitality businesses finance invoices fast.</h1>
              <p className="lead">Submit documents, choose fixed repayment terms (1, 3, or 6 months), and track approval and payments in one workflow.</p>
              <div className="cta-row">
                <Link to="/login" className="btn ghost">Login</Link>
                <Link to="/signup" className="btn ghost">Signup</Link>
              </div>
            </div>
          </section>

          <section className="landing-grid">
            <article><h3>1. Upload Required Documents</h3><p>Bank statements, financial statements, and supplier invoice.</p></article>
            <article><h3>2. Select Fixed Plan</h3><p>Choose 1, 3, or 6 months. No sales-cut repayment.</p></article>
            <article><h3>3. Admin Review</h3><p>Agent evaluates request and approves or rejects with notes.</p></article>
          </section>
        </div>
      </main>
    </div>
  );
}

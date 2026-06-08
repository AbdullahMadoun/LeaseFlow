import { Link, useParams } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import { useAuth } from "../context/AuthContext";
import { useData } from "../context/DataContext";
import StatusBadge from "../components/StatusBadge";
import { formatDate, toCurrency } from "../utils/helpers";

export default function RequestDetailPage() {
  const { id } = useParams();
  const { currentUser } = useAuth();
  const { getRequest } = useData();
  const req = getRequest(id);

  if (!req || req.customerId !== currentUser.id) {
    return (
      <DashboardLayout title="Request Detail">
        <section className="detail-empty">
          <h2>Request not found</h2>
          <p className="muted">This request is not available in your workspace.</p>
          <Link className="btn ghost" to="/dashboard">Back to Dashboard</Link>
        </section>
      </DashboardLayout>
    );
  }

  const timeline = [
    { label: "Draft Created", at: req.createdAt, show: Boolean(req.createdAt) },
    { label: "Submitted For Review", at: req.submittedAt, show: Boolean(req.submittedAt) },
    { label: "Decision Recorded", at: req.decisionAt, show: Boolean(req.decisionAt) }
  ].filter((item) => item.show);

  const totalFiles =
    req.documents.bankStatements.length +
    req.documents.financialStatements.length +
    req.documents.supplierInvoice.length;
  const isApproved = req.status === "approved";

  return (
    <DashboardLayout title="Request Detail">
      <section className="detail-hero">
        <div className="detail-hero-main">
          <p className="detail-eyebrow">Customer Request</p>
          <div className="detail-hero-head">
            <h1>Request Status</h1>
            <StatusBadge status={req.status} />
          </div>
          <p className="detail-id">{req.id}</p>
          <div className="detail-amount">{toCurrency(req.invoiceDetails.invoiceAmount || 0)}</div>
          <div className="detail-stats">
            <div>
              <span>Plan</span>
              <strong>{req.plan.durationMonths ? `${req.plan.durationMonths} month(s)` : "Not selected"}</strong>
            </div>
            <div>
              <span>Submitted</span>
              <strong>{req.submittedAt ? formatDate(req.submittedAt) : "Not submitted"}</strong>
            </div>
            <div>
              <span>Uploaded Files</span>
              <strong>{totalFiles}</strong>
            </div>
          </div>
        </div>

        <aside className="detail-hero-side">
          <h3>Actions</h3>
          <p className="muted">Review the current status and return to your workspace when finished.</p>
          <div className="detail-actions">
            {isApproved && <Link className="btn primary" to={`/payment-plan/${req.id}`}>Open Payment Plan</Link>}
          </div>
          <div className="detail-side-facts">
            <div>
              <span>Decision Date</span>
              <strong>{req.decisionAt ? formatDate(req.decisionAt) : "Pending"}</strong>
            </div>
            <div>
              <span>Review State</span>
              <strong>{isApproved ? "Approved and scheduled" : "Awaiting admin decision"}</strong>
            </div>
          </div>
        </aside>
      </section>

      <section className="detail-grid">
        <article className="detail-panel">
          <h3>Decision</h3>
          <div className="detail-info-list">
            <div>
              <span>Reason</span>
              <strong>{req.decisionReason || "No note yet"}</strong>
            </div>
            <div>
              <span>Bank Statements</span>
              <strong>{req.documents.bankStatements.length} uploaded</strong>
            </div>
            <div>
              <span>Financial Statements</span>
              <strong>{req.documents.financialStatements.length} uploaded</strong>
            </div>
            <div>
              <span>Supplier Invoices</span>
              <strong>{req.documents.supplierInvoice.length} uploaded</strong>
            </div>
          </div>
        </article>

        <article className="detail-panel">
          <h3>Timeline</h3>
          <div className="detail-timeline">
            {timeline.map((item) => (
              <div key={item.label} className="detail-timeline-item">
                <span className="detail-timeline-dot" />
                <div>
                  <strong>{item.label}</strong>
                  <p className="muted">{formatDate(item.at)}</p>
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <div className="detail-footer-actions">
        <Link className="btn ghost" to="/dashboard">Back to Dashboard</Link>
      </div>
    </DashboardLayout>
  );
}

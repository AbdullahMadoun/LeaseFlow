import { Link, useNavigate } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import { useAuth } from "../context/AuthContext";
import { useData } from "../context/DataContext";
import { toCurrency } from "../utils/helpers";

export default function RequestReviewPage() {
  const { currentUser } = useAuth();
  const { getOrCreateDraft, submitDraft } = useData();
  const navigate = useNavigate();
  const draft = getOrCreateDraft(currentUser.id);

  const totalFiles =
    draft.documents.bankStatements.length +
    draft.documents.financialStatements.length +
    draft.documents.supplierInvoice.length;
  const selectedPlanLabel = draft.plan.durationMonths
    ? `${draft.plan.durationMonths} Month${draft.plan.durationMonths > 1 ? "s" : ""}`
    : "Plan Missing";

  function onSubmit() {
    const result = submitDraft(currentUser.id);
    if (!result.ok) {
      alert(result.message);
      return;
    }
    navigate(`/requests/${result.requestId}`);
  }

  return (
    <DashboardLayout title="Review & Submit">
      <section className="review-hero review-hero-single">
        <div className="review-hero-main">
          <p className="detail-eyebrow">Final Review</p>
          <h1>Submit Your Financing Request</h1>
          <p className="muted">
            Confirm the business details and fixed repayment plan, then send the request for review.
          </p>
        </div>
      </section>

      <section className="review-summary-panel">
        <div className="review-summary-head">
          <div>
            <p className="review-summary-label">Business Summary</p>
            <h3>{draft.businessProfile.businessName}</h3>
          </div>
          <div className="review-chip-row">
            <span className="review-chip success">{totalFiles} files attached</span>
            <span className="review-chip">{selectedPlanLabel}</span>
          </div>
        </div>

        <div className="review-summary-grid">
          <div className="review-summary-block">
            <span>Business Type</span>
            <strong>{draft.businessProfile.businessType}</strong>
          </div>
          <div className="review-summary-block">
            <span>CR Number</span>
            <strong>{draft.businessProfile.crNumber}</strong>
          </div>
          <div className="review-summary-block">
            <span>IBAN</span>
            <strong>{draft.businessProfile.iban}</strong>
          </div>
          <div className="review-summary-block">
            <span>Repayment Plan</span>
            <strong>{selectedPlanLabel}</strong>
          </div>
          <div className="review-summary-block">
            <span>Processing Fee</span>
            <strong>{toCurrency(draft.plan.processingFee || 0)}</strong>
          </div>
          <div className="review-summary-block">
            <span>Required Uploads</span>
            <strong>{totalFiles}/3 ready</strong>
          </div>
        </div>
      </section>

      <div className="action-row">
        <Link className="btn ghost" to="/request/new">Back</Link>
        <button className="btn primary" type="button" onClick={onSubmit}>Submit Request</button>
      </div>
    </DashboardLayout>
  );
}

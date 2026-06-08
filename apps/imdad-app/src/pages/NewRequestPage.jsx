import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import { useAuth } from "../context/AuthContext";
import { useData } from "../context/DataContext";

function fileNames(fileList) {
  return Array.from(fileList || []).map((f) => ({ name: f.name, size: f.size }));
}

export default function NewRequestPage() {
  const { currentUser } = useAuth();
  const { getProfile, getOrCreateDraft, updateDraft } = useData();
  const navigate = useNavigate();
  const profile = getProfile(currentUser.id);
  const draft = getOrCreateDraft(currentUser.id);
  const [docs, setDocs] = useState(draft.documents);
  const legalBusinessName = profile?.businessName || "";
  const businessCategory = profile?.businessType || "Cafe";
  const planOptions = [
    { durationMonths: 1, label: "Short-Term", subtitle: "Immediate relief for quick turnover.", processingFee: 250, dueHint: "Oct 24, 2024" },
    { durationMonths: 3, label: "Growth", subtitle: "Optimized for seasonal hospitality cycles.", processingFee: 680, dueHint: "Dec 24, 2024", featured: true },
    { durationMonths: 6, label: "Stability", subtitle: "Maximum flexibility for large scale ops.", processingFee: 1200, dueHint: "Mar 24, 2025" }
  ];
  const [selectedPlan, setSelectedPlan] = useState(draft.plan.durationMonths || 3);

  function onFilesChange(key, files) {
    const mapped = fileNames(files);
    const next = { ...docs, [key]: mapped };
    setDocs(next);
    updateDraft(currentUser.id, {
      businessProfile: {
        ...(profile || {}),
        businessName: legalBusinessName,
        businessType: businessCategory
      },
      documents: next
    });
  }

  function onSelectPlan(durationMonths, processingFee) {
    setSelectedPlan(durationMonths);
    updateDraft(currentUser.id, {
      plan: { durationMonths, processingFee }
    });
  }

  function onContinue() {
    const chosenPlan = planOptions.find((plan) => plan.durationMonths === selectedPlan);
    updateDraft(currentUser.id, {
      businessProfile: {
        ...(profile || {}),
        businessName: legalBusinessName,
        businessType: businessCategory
      },
      documents: docs,
      plan: chosenPlan
        ? { durationMonths: chosenPlan.durationMonths, processingFee: chosenPlan.processingFee }
        : draft.plan
    });
    navigate("/request/review");
  }

  const hasRequiredDocs =
    docs.bankStatements.length > 0 &&
    docs.financialStatements.length > 0 &&
    docs.supplierInvoice.length > 0;
  const isComplete = hasRequiredDocs && Boolean(selectedPlan);

  return (
    <DashboardLayout title="New Financing Request">
      {!profile ? (
        <section className="table-wrap" style={{ padding: "1rem" }}>
          <h3>Business profile required</h3>
          <p className="muted">Complete your profile before creating a request.</p>
          <Link className="btn primary" to="/profile">Go to Profile</Link>
        </section>
      ) : (
        <>
          <section className="request-card">
            <h3 className="request-title">Business Identity</h3>
            <div className="identity-grid">
              <div>
                <label className="field-label">Legal Business Name</label>
                <div className="static-field">{legalBusinessName}</div>
              </div>
              <div>
                <label className="field-label">Business Category</label>
                <div className="static-field">{businessCategory}</div>
              </div>
            </div>
          </section>

          <section className="request-archives">
            <div className="archives-head">
              <h3 className="request-title">Financial Archives</h3>
              <span className="archives-note">Required: PDF or JPEG</span>
            </div>

            <div className="primary-upload">
              <input id="bank-statements" className="upload-input" type="file" multiple onChange={(e) => onFilesChange("bankStatements", e.target.files)} />
              <div className="upload-icon">BS</div>
              <h4>Bank Statements</h4>
              <p>Upload the last 6 months of corporate bank activity to verify liquidity patterns.</p>
              <label className="upload-link" htmlFor="bank-statements">
                {docs.bankStatements.length > 0 ? `${docs.bankStatements.length} file(s) selected` : "Select Files or Drag & Drop"}
              </label>
            </div>

            <div className="archive-grid">
              <div className="archive-tile">
                <input id="financial-statements" className="upload-input" type="file" multiple onChange={(e) => onFilesChange("financialStatements", e.target.files)} />
                <p className="tile-icon">FS</p>
                <h4>Financial Statements</h4>
                <p>Latest audited P&amp;L and Balance Sheet reports.</p>
                <div className="tile-foot">
                  <span>{docs.financialStatements.length} Files</span>
                  <label htmlFor="financial-statements">+</label>
                </div>
              </div>
              <div className="archive-tile">
                <input id="supplier-invoice" className="upload-input" type="file" multiple onChange={(e) => onFilesChange("supplierInvoice", e.target.files)} />
                <p className="tile-icon">SI</p>
                <h4>Supplier Invoices</h4>
                <p>Current pending invoices for financing consideration.</p>
                <div className="tile-foot">
                  <span>{docs.supplierInvoice.length} Files</span>
                  <label htmlFor="supplier-invoice">+</label>
                </div>
              </div>
            </div>
          </section>

          <section className="request-archives">
            <div className="archives-head">
              <h3 className="request-title">Select Your Plan</h3>
              <span className="muted">Choose the financing structure that best aligns with your cash flow.</span>
            </div>
            <div className="plan-showcase">
              {planOptions.map((plan) => {
                const active = selectedPlan === plan.durationMonths;
                return (
                  <button
                    key={plan.durationMonths}
                    type="button"
                    className={active ? "plan-showcase-card active" : "plan-showcase-card"}
                    onClick={() => onSelectPlan(plan.durationMonths, plan.processingFee)}
                  >
                    {plan.featured && <span className="featured-pill">Most Balanced</span>}
                    <span className="mini-pill">{plan.label}</span>
                    <h4>{plan.durationMonths} Month{plan.durationMonths > 1 ? "s" : ""}</h4>
                    <p>{plan.subtitle}</p>
                    <div className="plan-meta">
                      <small>Processing Fee</small>
                      <strong>SAR {plan.processingFee.toLocaleString()}</strong>
                    </div>
                    <div className="plan-meta">
                      <small>Due Date</small>
                      <strong>{plan.dueHint}</strong>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <div className="action-row">
            <Link className="btn ghost" to="/profile">Edit Profile</Link>
            <button className={isComplete ? "btn primary" : "btn ghost disabled"} type="button" onClick={onContinue}>Continue to Review</button>
          </div>
        </>
      )}
    </DashboardLayout>
  );
}

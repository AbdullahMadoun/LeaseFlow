import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import { useAuth } from "../context/AuthContext";
import { useData } from "../context/DataContext";
import StatusBadge from "../components/StatusBadge";
import { formatDate, toCurrency } from "../utils/helpers";

const defaultEval = {
  bankStatements: { score: "", summary: "", feedback: "" },
  financialStatements: { score: "", summary: "", feedback: "" },
  samaInfo: { score: "", summary: "", feedback: "" },
  googleMapsReview: { score: "", summary: "", feedback: "" }
};

export default function AdminReviewPage() {
  const { id } = useParams();
  const { currentUser } = useAuth();
  const { getRequest, updateEvaluation, approveRequest, rejectRequest } = useData();
  const navigate = useNavigate();
  const req = getRequest(id);
  const [note, setNote] = useState("");
  const [evalState, setEvalState] = useState(defaultEval);

  useEffect(() => {
    if (req?.evaluation) {
      setEvalState({ ...defaultEval, ...req.evaluation });
    }
    setNote(req?.decisionReason || "");
  }, [req]);

  const canReject = useMemo(() => req && req.status !== "approved", [req]);
  const readiness = useMemo(() => {
    const keys = ["bankStatements", "financialStatements", "samaInfo", "googleMapsReview"];
    const values = keys
      .map((k) => Number(evalState[k]?.score))
      .filter((n) => !Number.isNaN(n) && Number.isFinite(n));
    if (!values.length) return null;
    return Math.round(values.reduce((a, b) => a + b, 0) / values.length);
  }, [evalState]);

  if (!req) {
    return (
      <DashboardLayout title="Admin Review" admin>
        <p>Request not found.</p>
      </DashboardLayout>
    );
  }

  function saveEval() {
    updateEvaluation(req.id, evalState);
  }

  function onApprove() {
    saveEval();
    approveRequest(req.id, currentUser.id, note);
    navigate("/admin/requests");
  }

  function onReject() {
    saveEval();
    const result = rejectRequest(req.id, currentUser.id, note);
    if (!result.ok) {
      alert(result.message);
      return;
    }
    navigate("/admin/requests");
  }

  function EvalBlock({ title, keyName }) {
    const value = evalState[keyName];
    return (
      <article>
        <h3>{title}</h3>
        <label>Score / Status</label>
        <input value={value.score} onChange={(e) => setEvalState((p) => ({ ...p, [keyName]: { ...p[keyName], score: e.target.value } }))} />
        <label>Summary</label>
        <input value={value.summary} onChange={(e) => setEvalState((p) => ({ ...p, [keyName]: { ...p[keyName], summary: e.target.value } }))} />
        <label>Feedback / Details</label>
        <input value={value.feedback} onChange={(e) => setEvalState((p) => ({ ...p, [keyName]: { ...p[keyName], feedback: e.target.value } }))} />
      </article>
    );
  }

  return (
    <DashboardLayout title="Admin Review" admin>
      <section className="form-grid">
        <article>
          <h3>Request Summary</h3>
          <p><strong>ID:</strong> {req.id}</p>
          <p><strong>Status:</strong> <StatusBadge status={req.status} /></p>
          <p><strong>Business:</strong> {req.businessProfile.businessName || "-"}</p>
          <p><strong>Owner:</strong> {req.businessProfile.ownerName || "-"}</p>
          <p><strong>Business Type:</strong> {req.businessProfile.businessType || "-"}</p>
          <p><strong>Invoice Amount:</strong> {toCurrency(req.invoiceDetails.invoiceAmount || 0)}</p>
          <p><strong>Plan:</strong> {req.plan.durationMonths ? `${req.plan.durationMonths} month(s)` : "-"}</p>
          <p><strong>Submitted:</strong> {req.submittedAt ? formatDate(req.submittedAt) : "Not submitted"}</p>
        </article>
        <article>
          <h3>Documents</h3>
          <p>Bank Statements: {req.documents.bankStatements.length}</p>
          <p>Financial Statements: {req.documents.financialStatements.length}</p>
          <p>Supplier Invoice: {req.documents.supplierInvoice.length}</p>
          <p className="muted">Evaluation categories below include Bank Statements, Financial Statements, منصة سما info, and Google Maps review.</p>
        </article>
      </section>

      <section className="form-grid" style={{ marginTop: "1rem" }}>
        <EvalBlock title="Bank Statements" keyName="bankStatements" />
        <EvalBlock title="Financial Statements" keyName="financialStatements" />
        <EvalBlock title="منصة سما Information" keyName="samaInfo" />
        <EvalBlock title="Google Maps Review" keyName="googleMapsReview" />
      </section>

      <section className="table-wrap" style={{ marginTop: "1rem", padding: "1rem" }}>
        <h3>Full Report / Admin Notes</h3>
        <p className="muted">Business overview, financial analysis, risk flags, strengths, weaknesses, recommendation.</p>
        <p><strong>Readiness Score:</strong> {readiness === null ? "Not enough scored categories" : `${readiness}/100`}</p>
        {readiness !== null && (
          <div className="progress-line">
            <span style={{ width: `${Math.max(0, Math.min(readiness, 100))}%` }} />
          </div>
        )}
        <label>Admin Note</label>
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Decision rationale" />
      </section>

      <div className="action-row">
        <button className="btn ghost" type="button" onClick={saveEval}>Save Evaluation</button>
        {canReject ? <button className="btn danger" type="button" onClick={onReject}>Reject</button> : <button className="btn danger" type="button" disabled>Reject Disabled (Already Approved)</button>}
        <button className="btn primary" type="button" onClick={onApprove}>{req.status === "rejected" ? "Approve Rejected Request" : "Approve"}</button>
      </div>
    </DashboardLayout>
  );
}

import { Link } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import { useAuth } from "../context/AuthContext";
import { useData } from "../context/DataContext";
import InstallmentBlocks from "../components/InstallmentBlocks";
import StatusBadge from "../components/StatusBadge";
import { formatDate, toCurrency } from "../utils/helpers";

export default function UserDashboardPage() {
  const { currentUser } = useAuth();
  const { listUserRequests, payInstallment } = useData();
  const requests = listUserRequests(currentUser.id);
  const approved = requests.find((request) => request.status === "approved" && request.paymentPlan);
  const requestCount = requests.length;

  const installments = approved?.paymentPlan?.installments || [];
  const totalRepayment = approved?.paymentPlan?.totalRepayment || 0;
  const remaining = approved?.paymentPlan?.remainingBalance || 0;
  const paid = Math.max(totalRepayment - remaining, 0);

  return (
    <DashboardLayout title="Dashboard">
      <div className="dashboard-topbar">
        <Link className="btn primary" to="/request/new">Make Request</Link>
      </div>

      <section className="kpi-row">
        <article><p>Paid</p><h2>{toCurrency(paid)}</h2></article>
        <article><p>Remaining</p><h2>{toCurrency(remaining)}</h2></article>
        <article><p>Total Plan</p><h2>{toCurrency(totalRepayment)}</h2></article>
      </section>

      <section className="table-wrap" style={{ marginBottom: "1rem" }}>
        <header><h3>Planned Payments</h3></header>
        {approved ? (
          <div className="installment-panel">
            <InstallmentBlocks
              installments={installments}
              onPay={(installmentId) => payInstallment(approved.id, installmentId)}
            />
          </div>
        ) : (
          <div style={{ padding: "1rem" }}>
            <p className="muted">No approved payment plan yet. Once approved, your payment schedule will appear here.</p>
          </div>
        )}
      </section>

      <section className="table-wrap">
        <header>
          <h3>Submitted Requests</h3>
          <p className="muted" style={{ marginTop: "0.25rem" }}>
            {requestCount} request{requestCount === 1 ? "" : "s"} in your workspace.
          </p>
        </header>
        {requests.length > 0 ? (
          <>
            <div className="table-head">
              <span>Request</span>
              <span>Submitted</span>
              <span>Plan</span>
              <span>Status</span>
            </div>
            {requests.map((request) => (
              <div key={request.id} className="table-row">
                <span>
                  <Link to={`/requests/${request.id}`}>{request.id}</Link>
                </span>
                <span>{request.submittedAt ? formatDate(request.submittedAt) : formatDate(request.createdAt)}</span>
                <span>
                  {request.plan?.durationMonths
                    ? `${request.plan.durationMonths} month${request.plan.durationMonths > 1 ? "s" : ""}`
                    : "Not selected"}
                </span>
                <StatusBadge status={request.status} />
              </div>
            ))}
          </>
        ) : (
          <div style={{ padding: "1rem" }}>
            <p className="muted">You have not submitted any requests yet.</p>
          </div>
        )}
      </section>
    </DashboardLayout>
  );
}

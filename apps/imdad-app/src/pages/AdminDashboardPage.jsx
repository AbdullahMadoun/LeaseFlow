import { Link } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import { useData } from "../context/DataContext";
import StatusBadge from "../components/StatusBadge";
import { formatDate, toCurrency } from "../utils/helpers";

export default function AdminDashboardPage() {
  const { listAdminRequests } = useData();
  const rows = listAdminRequests();
  const underReview = rows.filter((r) => r.status === "under_review");
  const urgentCount = underReview.filter((r) => {
    if (!r.submittedAt) return false;
    const hours = (Date.now() - new Date(r.submittedAt).getTime()) / (1000 * 60 * 60);
    return hours >= 48;
  }).length;
  const latestActivity = rows.slice(0, 5);

  return (
    <DashboardLayout title="Admin Dashboard" admin>
      <section className="kpi-row">
        <article><p>Total Requests</p><h2>{rows.length}</h2></article>
        <article><p>Under Review</p><h2>{underReview.length}</h2></article>
        <article><p>Approved</p><h2>{rows.filter((r) => r.status === "approved").length}</h2></article>
      </section>

      <section className="table-wrap" style={{ padding: "1rem" }}>
        <h3>Operational Summary</h3>
        <p>Rejected: {rows.filter((r) => r.status === "rejected").length}</p>
        <p>Urgent under-review (48h+): {urgentCount}</p>
        <Link className="btn primary" to="/admin/requests">Open All Requests</Link>
      </section>

      <section className="table-wrap" style={{ marginTop: "1rem" }}>
        <header><h3>Latest Activity</h3></header>
        <div className="table-head"><span>Request</span><span>Date</span><span>Amount</span><span>Status</span></div>
        {latestActivity.map((r) => (
          <div className="table-row" key={r.id}>
            <span><Link to={`/admin/review/${r.id}`}>{r.id}</Link> | {r.businessProfile.businessName || "-"}</span>
            <span>{formatDate(r.submittedAt || r.createdAt)}</span>
            <span>{toCurrency(r.invoiceDetails.invoiceAmount || 0)}</span>
            <StatusBadge status={r.status} />
          </div>
        ))}
      </section>
    </DashboardLayout>
  );
}

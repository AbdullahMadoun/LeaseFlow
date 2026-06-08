import { Link } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import { useAuth } from "../context/AuthContext";
import { useData } from "../context/DataContext";
import StatusBadge from "../components/StatusBadge";
import { formatDate, toCurrency } from "../utils/helpers";

export default function RequestHistoryPage() {
  const { currentUser } = useAuth();
  const { listUserRequests } = useData();
  const rows = listUserRequests(currentUser.id);

  return (
    <DashboardLayout title="Request History">
      <section className="table-wrap">
        <header><h3>All Requests</h3></header>
        <div className="table-head"><span>Request ID</span><span>Submitted</span><span>Plan</span><span>Status</span></div>
        {rows.map((r) => (
          <div className="table-row" key={r.id}>
            <span><Link to={`/requests/${r.id}`}>{r.id}</Link></span>
            <span>{r.submittedAt ? formatDate(r.submittedAt) : formatDate(r.createdAt)}</span>
            <span>{r.plan.durationMonths ? `${r.plan.durationMonths}m (${toCurrency(r.plan.processingFee)})` : "Not set"}</span>
            <StatusBadge status={r.status} />
          </div>
        ))}
      </section>
    </DashboardLayout>
  );
}

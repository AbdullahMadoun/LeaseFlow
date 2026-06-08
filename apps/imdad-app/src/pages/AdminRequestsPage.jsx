import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import { useData } from "../context/DataContext";
import StatusBadge from "../components/StatusBadge";
import { formatDate, toCurrency } from "../utils/helpers";

export default function AdminRequestsPage() {
  const { listAdminRequests } = useData();
  const [filter, setFilter] = useState("all");
  const rows = listAdminRequests();

  const filtered = useMemo(() => {
    if (filter === "all") return rows;
    return rows.filter((r) => r.status === filter);
  }, [rows, filter]);

  return (
    <DashboardLayout title="Admin Requests" admin>
      <section className="action-row" style={{ justifyContent: "flex-start" }}>
        <button className={filter === "all" ? "btn primary" : "btn ghost"} onClick={() => setFilter("all")} type="button">All</button>
        <button className={filter === "under_review" ? "btn primary" : "btn ghost"} onClick={() => setFilter("under_review")} type="button">Under Review</button>
        <button className={filter === "approved" ? "btn primary" : "btn ghost"} onClick={() => setFilter("approved")} type="button">Approved</button>
        <button className={filter === "rejected" ? "btn primary" : "btn ghost"} onClick={() => setFilter("rejected")} type="button">Rejected</button>
      </section>

      <section className="table-wrap">
        <header><h3>Submitted Requests</h3></header>
        <div className="table-head"><span>Request / Business</span><span>Submission</span><span>Amount / Plan</span><span>Status</span></div>
        {filtered.map((r) => (
          <div className="table-row" key={r.id}>
            <span><Link to={`/admin/review/${r.id}`}>{r.id}</Link> | {r.businessProfile.businessName || "-"} | {r.businessProfile.ownerName || "-"} | {r.businessProfile.businessType || "-"}</span>
            <span>{r.submittedAt ? formatDate(r.submittedAt) : formatDate(r.createdAt)}</span>
            <span>{toCurrency(r.invoiceDetails.invoiceAmount || 0)} | {r.plan.durationMonths ? `${r.plan.durationMonths}m` : "-"}</span>
            <StatusBadge status={r.status} />
          </div>
        ))}
      </section>
    </DashboardLayout>
  );
}

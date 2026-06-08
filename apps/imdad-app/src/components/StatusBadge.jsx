export default function StatusBadge({ status }) {
  const value = (status || "").toLowerCase();
  const tone =
    value === "approved" || value === "repaying" || value === "paid"
      ? "ok"
      : value === "rejected" || value === "overdue" || value === "urgent"
        ? "danger"
        : "pending";

  return <span className={`badge ${tone}`}>{status}</span>;
}

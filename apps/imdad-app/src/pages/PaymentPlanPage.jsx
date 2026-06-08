import { useParams } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import { useAuth } from "../context/AuthContext";
import { useData } from "../context/DataContext";
import InstallmentBlocks from "../components/InstallmentBlocks";
import { daysUntil, formatDate, toCurrency } from "../utils/helpers";

export default function PaymentPlanPage() {
  const { id } = useParams();
  const { currentUser } = useAuth();
  const { getRequest, payInstallment } = useData();
  const req = getRequest(id);

  if (!req || req.customerId !== currentUser.id || req.status !== "approved" || !req.paymentPlan) {
    return (
      <DashboardLayout title="Payment Plan">
        <p>No approved payment plan found for this request.</p>
      </DashboardLayout>
    );
  }

  const plan = req.paymentPlan;
  const paidCount = plan.installments.filter((installment) => installment.status === "paid").length;
  const progressPercent = plan.installments.length
    ? Math.round((paidCount / plan.installments.length) * 100)
    : 0;
  const overdueCount = plan.installments.filter((installment) => installment.status !== "paid" && daysUntil(installment.dueDate) < 0).length;

  return (
    <DashboardLayout title="Payment Plan">
      <section className="kpi-row">
        <article><p>Approved Amount</p><h2>{toCurrency(plan.approvedAmount)}</h2></article>
        <article><p>Remaining Balance</p><h2>{toCurrency(plan.remainingBalance)}</h2></article>
        <article><p>Next Due Date</p><h2>{plan.nextDueDate ? formatDate(plan.nextDueDate) : "-"}</h2></article>
      </section>

      <section className="table-wrap" style={{ padding: "1rem" }}>
        <h3>Repayment Progress</h3>
        <p>Duration: {req.plan.durationMonths} month(s) | Total Repayment: {toCurrency(plan.totalRepayment)} | Progress: {progressPercent}%</p>
        <div className="progress-line">
          <span style={{ width: `${progressPercent}%` }} />
        </div>
        <div className="chip-row">
          <span className="chip done">Paid: {paidCount}</span>
          <span className={`chip ${overdueCount > 0 ? "" : "done"}`}>Overdue: {overdueCount}</span>
          <span className="chip">Unpaid: {plan.installments.length - paidCount}</span>
        </div>
      </section>

      <section className="table-wrap" style={{ marginTop: "1rem" }}>
        <header><h3>Installments</h3></header>
        <div className="installment-panel">
          <InstallmentBlocks
            installments={plan.installments}
            onPay={(installmentId) => payInstallment(req.id, installmentId)}
          />
        </div>
      </section>
    </DashboardLayout>
  );
}

import { daysUntil, toCurrency } from "../utils/helpers";

function InstallmentIcon({ variant }) {
  if (variant === "paid") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="9" fill="currentColor" opacity="0.12" />
        <path d="M8.5 12.2l2.2 2.3 4.8-5.3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  if (variant === "upcoming") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M8 3h8M8 21h8M9 3v3l2.8 3.2a4 4 0 010 5.6L9 18v3M15 3v3l-2.8 3.2a4 4 0 000 5.6L15 18v3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  if (variant === "overdue") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 7v5M12 16h.01" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M10.3 3.8L2.8 17a2 2 0 001.7 3h15a2 2 0 001.7-3L13.7 3.8a2 2 0 00-3.4 0z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="6" y="10" width="12" height="9" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M9 10V8a3 3 0 016 0v2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export default function InstallmentBlocks({ installments, onPay }) {
  const nextOpenId = installments.find((installment) => installment.status !== "paid")?.id || null;

  return (
    <div className="installment-grid">
      {installments.map((installment) => {
        const remainingDays = daysUntil(installment.dueDate);
        const isPaid = installment.status === "paid";
        const isOverdue = !isPaid && remainingDays < 0;
        const isUpcoming = !isPaid && !isOverdue && installment.id === nextOpenId;
        const variant = isPaid ? "paid" : isOverdue ? "overdue" : isUpcoming ? "upcoming" : "pending";
        const statusLabel = isPaid ? "Settled" : isOverdue ? "Overdue" : isUpcoming ? "Upcoming" : "Pending";
        const remainingLabel = isOverdue
          ? `${Math.abs(remainingDays)} day${Math.abs(remainingDays) === 1 ? "" : "s"} overdue`
          : `Due in ${remainingDays} day${remainingDays === 1 ? "" : "s"}`;
        const amountLabel = isPaid ? "Amount Paid" : isUpcoming || isOverdue ? "Amount Due" : "Scheduled Amount";
        const canPay = Boolean(onPay) && !isPaid;
        const actionLabel = isPaid ? "Settled" : isUpcoming || isOverdue ? "Pay Now" : "Pay Early";

        return (
          <article key={installment.id} className={`installment-card ${variant}`}>
            <div className="installment-card-top">
              <div className={`installment-icon ${variant}`}>
                <InstallmentIcon variant={variant} />
              </div>

              <div className="installment-card-copy">
                <p className="installment-kicker">Payment {installment.number}</p>
                <span className={`installment-pill ${variant}`}>{statusLabel}</span>
              </div>
            </div>

            <div className="installment-card-body">
              <div className="installment-card-meta">
                <div>
                  <span>Remaining Time</span>
                  <strong>{isPaid ? "Completed" : remainingLabel}</strong>
                </div>
              </div>

              <div className="installment-amount">
                <span>{amountLabel}</span>
                <strong>{toCurrency(installment.amount)}</strong>
              </div>
            </div>

            {onPay ? (
              <button
                type="button"
                className={canPay ? `btn installment-pay ${variant}` : "btn ghost disabled installment-pay"}
                onClick={() => canPay && onPay(installment.id)}
                disabled={!canPay}
              >
                {actionLabel}
              </button>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

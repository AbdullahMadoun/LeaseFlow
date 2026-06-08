"""Generate a fake KSA bank statement PDF.

Output: (pdf_bytes, BankStatementReport) where the report carries the
same numbers that appear in the PDF. Extractor should round-trip.
"""
from __future__ import annotations

import io
from datetime import date, timedelta
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..schemas.documents import (
    BankAggregates,
    BankMonth,
    BankStatementReport,
    ExtractionMeta,
)
from ._common import BANK_NAMES, daterange_months, sar, seed_rng


def generate_bank_statement(
    *,
    seed: str,
    business_name: str,
    months: int = 6,
    monthly_revenue_target_sar: float = 80000,
    volatility: float = 0.18,
    expense_ratio: float = 0.72,
    bounces: int = 0,
    overdrafts: int = 0,
    end_date: date | None = None,
) -> tuple[bytes, BankStatementReport]:
    rng = seed_rng(seed, "bank_statement")
    end = end_date or date.today().replace(day=1) - timedelta(days=1)
    month_starts = daterange_months(end, months)

    bank = rng.choice(BANK_NAMES)
    iban_last4 = f"{rng.randint(1000, 9999)}"

    # Generate per-month revenue + expenses with volatility + mild trend
    trend_slope = rng.uniform(-0.06, 0.10)  # -6% to +10% over the window
    monthly_data: list[BankMonth] = []
    running_balance = rng.uniform(25000, 80000)

    for i, m_start in enumerate(month_starts):
        trend_factor = 1 + trend_slope * (i / max(1, months - 1))
        rev = monthly_revenue_target_sar * trend_factor * rng.uniform(1 - volatility, 1 + volatility)
        exp = rev * expense_ratio * rng.uniform(0.92, 1.08)
        net = rev - exp
        txn_count = int(rng.uniform(180, 480) * trend_factor)
        running_balance += net
        monthly_data.append(BankMonth(
            month=m_start.strftime("%Y-%m"),
            revenue_sar=round(rev, 2),
            expenses_sar=round(exp, 2),
            net_sar=round(net, 2),
            txn_count=txn_count,
            source_pages=[i + 1],  # one page per month
        ))

    # aggregates
    revs = [m.revenue_sar for m in monthly_data]
    exps = [m.expenses_sar for m in monthly_data]
    nets = [m.net_sar for m in monthly_data]
    mean_net = sum(nets) / len(nets)
    std_net = (sum((n - mean_net) ** 2 for n in nets) / len(nets)) ** 0.5
    vol = (std_net / max(1, abs(mean_net)))
    # trend classification
    first_half = sum(nets[: len(nets) // 2]) / max(1, len(nets) // 2)
    second_half = sum(nets[len(nets) // 2:]) / max(1, len(nets) - len(nets) // 2)
    delta = (second_half - first_half) / max(1, abs(first_half))
    trend: Any = "up" if delta > 0.05 else ("down" if delta < -0.05 else "stable")

    aggregates = BankAggregates(
        monthly_revenue_avg_sar=round(sum(revs) / len(revs), 2),
        monthly_expenses_avg_sar=round(sum(exps) / len(exps), 2),
        monthly_net_avg_sar=round(mean_net, 2),
        volatility=round(vol, 3),
        trend=trend,
        bounced_count=bounces,
        overdraft_events=overdrafts,
    )

    report = BankStatementReport(
        bank_name=bank,
        account_holder=business_name,
        iban_last4=iban_last4,
        period_start=month_starts[0].strftime("%Y-%m-%d"),
        period_end=(month_starts[-1] + timedelta(days=30)).strftime("%Y-%m-%d"),
        monthly=monthly_data,
        aggregates=aggregates,
        flags=(["bounces_present"] if bounces else []) + (["overdraft_present"] if overdrafts else []),
        meta=ExtractionMeta(confidence=1.0, source_filename="bank_statement.pdf"),
    )

    pdf_bytes = _render_pdf(bank, business_name, iban_last4, monthly_data, aggregates, running_balance)
    return pdf_bytes, report


def _render_pdf(bank: str, account_holder: str, iban_last4: str,
                monthly: list[BankMonth], agg: BankAggregates,
                closing_balance: float) -> bytes:
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    flow: list[Any] = []

    # --- header
    flow.append(Paragraph(f"<b>{bank}</b>", styles["Title"]))
    flow.append(Spacer(1, 0.2 * cm))
    flow.append(Paragraph(f"<b>Account Statement</b> — {account_holder}", styles["Normal"]))
    flow.append(Paragraph(
        f"IBAN: SA00 {bank[:4].upper()} **** **** **** {iban_last4} &nbsp;&nbsp;|&nbsp;&nbsp; Currency: SAR",
        styles["Normal"],
    ))
    period_start = monthly[0].month
    period_end = monthly[-1].month
    flow.append(Paragraph(f"Period: {period_start} to {period_end}", styles["Normal"]))
    flow.append(Spacer(1, 0.4 * cm))

    # --- summary table
    summary_rows = [
        ["Monthly Revenue (avg)", sar(agg.monthly_revenue_avg_sar or 0)],
        ["Monthly Expenses (avg)", sar(agg.monthly_expenses_avg_sar or 0)],
        ["Monthly Net (avg)", sar(agg.monthly_net_avg_sar or 0)],
        ["Volatility", f"{agg.volatility:.3f}" if agg.volatility else "—"],
        ["Trend", agg.trend or "—"],
        ["Bounced payments", str(agg.bounced_count)],
        ["Overdraft events", str(agg.overdraft_events)],
        ["Closing balance", sar(closing_balance)],
    ]
    t = Table(summary_rows, colWidths=[6 * cm, 6 * cm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 0.6 * cm))

    # --- one page per month with monthly summary table
    for i, m in enumerate(monthly):
        if i > 0:
            flow.append(PageBreak())
        flow.append(Paragraph(f"<b>Monthly Summary — {m.month}</b>", styles["Heading2"]))
        flow.append(Spacer(1, 0.3 * cm))
        rows = [
            ["Month", m.month],
            ["Revenue", sar(m.revenue_sar)],
            ["Expenses", sar(m.expenses_sar)],
            ["Net", sar(m.net_sar)],
            ["Transactions", str(m.txn_count)],
        ]
        t2 = Table(rows, colWidths=[6 * cm, 6 * cm])
        t2.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
        ]))
        flow.append(t2)
        flow.append(Spacer(1, 0.3 * cm))
        flow.append(Paragraph(
            f"Representative deposits and withdrawals for {m.month}. Revenue reflects "
            f"card settlements and bank transfers from sales. Expenses include supplier "
            f"payments, rent, salaries, and utilities.",
            styles["Normal"],
        ))

    doc.build(flow)
    return buf.getvalue()

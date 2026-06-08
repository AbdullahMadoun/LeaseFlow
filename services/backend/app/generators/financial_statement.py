"""Generate a fake financial statement PDF (balance sheet + income statement)."""
from __future__ import annotations

import io
from datetime import date
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..schemas.documents import (
    BalanceSheet,
    ExtractionMeta,
    FinancialRatios,
    FinancialStatementReport,
    IncomeStatement,
)
from ._common import sar, seed_rng


def generate_financial_statement(
    *,
    seed: str,
    business_name: str,
    period_end: date | None = None,
    annual_revenue_sar: float = 960000,
    gross_margin: float = 0.52,
    opex_ratio: float = 0.30,
    debt_to_equity: float = 0.72,
) -> tuple[bytes, FinancialStatementReport]:
    rng = seed_rng(seed, "financial_statement")
    period_end = period_end or date(date.today().year - 1, 12, 31)
    period_start = date(period_end.year, 1, 1)

    # Income statement
    revenue = annual_revenue_sar * rng.uniform(0.92, 1.08)
    cogs = revenue * (1 - gross_margin) * rng.uniform(0.95, 1.05)
    opex = revenue * opex_ratio * rng.uniform(0.9, 1.1)
    net_profit = revenue - cogs - opex

    # Balance sheet
    current_assets = revenue * rng.uniform(0.15, 0.30)
    non_current_assets = revenue * rng.uniform(0.20, 0.40)
    total_assets = current_assets + non_current_assets

    equity_ratio = 1 / (1 + debt_to_equity)
    equity = total_assets * equity_ratio
    total_liabilities = total_assets - equity
    current_liabilities = total_liabilities * rng.uniform(0.35, 0.65)

    income = IncomeStatement(
        revenue_sar=round(revenue, 2),
        cogs_sar=round(cogs, 2),
        opex_sar=round(opex, 2),
        net_profit_sar=round(net_profit, 2),
        source_pages=[2],
    )
    balance = BalanceSheet(
        total_assets_sar=round(total_assets, 2),
        total_liabilities_sar=round(total_liabilities, 2),
        equity_sar=round(equity, 2),
        current_assets_sar=round(current_assets, 2),
        current_liabilities_sar=round(current_liabilities, 2),
        source_pages=[1],
    )
    ratios = FinancialRatios(
        current_ratio=round(current_assets / max(1, current_liabilities), 2),
        debt_to_equity=round(total_liabilities / max(1, equity), 2),
        gross_margin=round((revenue - cogs) / max(1, revenue), 3),
        net_margin=round(net_profit / max(1, revenue), 3),
    )

    report = FinancialStatementReport(
        company_name=business_name,
        period_start=period_start.strftime("%Y-%m-%d"),
        period_end=period_end.strftime("%Y-%m-%d"),
        balance_sheet=balance,
        income_statement=income,
        ratios=ratios,
        meta=ExtractionMeta(confidence=1.0, source_filename="financial_statement.pdf"),
    )
    pdf_bytes = _render(business_name, period_start, period_end, income, balance, ratios)
    return pdf_bytes, report


def _render(business: str, p_start: date, p_end: date,
            income: IncomeStatement, balance: BalanceSheet,
            ratios: FinancialRatios) -> bytes:
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    flow: list[Any] = []

    # Page 1 — Balance Sheet
    flow.append(Paragraph(f"<b>{business}</b>", styles["Title"]))
    flow.append(Paragraph(f"Financial Statements — Period {p_start} to {p_end}", styles["Normal"]))
    flow.append(Spacer(1, 0.6 * cm))
    flow.append(Paragraph("<b>Balance Sheet</b>", styles["Heading2"]))
    flow.append(Spacer(1, 0.3 * cm))

    bs_rows = [
        ["Total Assets", sar(balance.total_assets_sar or 0)],
        ["  Current Assets", sar(balance.current_assets_sar or 0)],
        ["  Non-Current Assets", sar((balance.total_assets_sar or 0) - (balance.current_assets_sar or 0))],
        ["Total Liabilities", sar(balance.total_liabilities_sar or 0)],
        ["  Current Liabilities", sar(balance.current_liabilities_sar or 0)],
        ["  Long-Term Liabilities", sar((balance.total_liabilities_sar or 0) - (balance.current_liabilities_sar or 0))],
        ["Equity", sar(balance.equity_sar or 0)],
    ]
    t = Table(bs_rows, colWidths=[8 * cm, 6 * cm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    flow.append(t)

    flow.append(PageBreak())

    # Page 2 — Income Statement + ratios
    flow.append(Paragraph("<b>Income Statement</b>", styles["Heading2"]))
    flow.append(Spacer(1, 0.3 * cm))
    is_rows = [
        ["Revenue", sar(income.revenue_sar or 0)],
        ["Cost of Goods Sold", sar(income.cogs_sar or 0)],
        ["Operating Expenses", sar(income.opex_sar or 0)],
        ["Net Profit", sar(income.net_profit_sar or 0)],
    ]
    t2 = Table(is_rows, colWidths=[8 * cm, 6 * cm])
    t2.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    flow.append(t2)

    flow.append(Spacer(1, 0.6 * cm))
    flow.append(Paragraph("<b>Key Ratios</b>", styles["Heading3"]))
    r_rows = [
        ["Current Ratio", f"{ratios.current_ratio or 0:.2f}"],
        ["Debt-to-Equity", f"{ratios.debt_to_equity or 0:.2f}"],
        ["Gross Margin", f"{(ratios.gross_margin or 0) * 100:.1f}%"],
        ["Net Margin", f"{(ratios.net_margin or 0) * 100:.1f}%"],
    ]
    t3 = Table(r_rows, colWidths=[8 * cm, 6 * cm])
    t3.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    flow.append(t3)

    doc.build(flow)
    return buf.getvalue()

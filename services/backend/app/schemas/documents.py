"""Per-document extractor output schemas.

ONE source of truth for each doc type. Generators produce instances of these;
extractors return instances of these; documents.analysis_report is a serialized
instance of these.

Every field that represents a number from the source document includes
source_pages so an auditor can open the PDF to that page and verify.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SchemaVersion = Literal["v1"]


class ExtractionMeta(BaseModel):
    """Shared metadata on every extractor output."""
    schema_version: SchemaVersion = "v1"
    extractor_version: str = "v1"
    confidence: float = Field(ge=0, le=1)
    low_confidence_fields: list[str] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)
    source_filename: str | None = None


# ============================================================
# bank_statement
# ============================================================

class BankMonth(BaseModel):
    month: str              # ISO yyyy-mm
    revenue_sar: float
    expenses_sar: float
    net_sar: float
    txn_count: int
    source_pages: list[int] = Field(default_factory=list)


class BankAggregates(BaseModel):
    monthly_revenue_avg_sar: float | None = None
    monthly_expenses_avg_sar: float | None = None
    monthly_net_avg_sar: float | None = None
    volatility: float | None = None              # 0-1, std/mean of monthly net
    trend: Literal["up", "stable", "down"] | None = None
    bounced_count: int = 0
    overdraft_events: int = 0


class BankStatementReport(BaseModel):
    doc_type: Literal["bank_statement"] = "bank_statement"
    bank_name: str | None = None
    account_holder: str | None = None
    iban_last4: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    currency: str = "SAR"
    monthly: list[BankMonth] = Field(default_factory=list)
    aggregates: BankAggregates = Field(default_factory=BankAggregates)
    flags: list[str] = Field(default_factory=list)
    meta: ExtractionMeta


# ============================================================
# financial_statement
# ============================================================

class BalanceSheet(BaseModel):
    total_assets_sar: float | None = None
    total_liabilities_sar: float | None = None
    equity_sar: float | None = None
    current_assets_sar: float | None = None
    current_liabilities_sar: float | None = None
    source_pages: list[int] = Field(default_factory=list)


class IncomeStatement(BaseModel):
    revenue_sar: float | None = None
    cogs_sar: float | None = None
    opex_sar: float | None = None
    net_profit_sar: float | None = None
    source_pages: list[int] = Field(default_factory=list)


class FinancialRatios(BaseModel):
    current_ratio: float | None = None
    debt_to_equity: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None


class FinancialStatementReport(BaseModel):
    doc_type: Literal["financial_statement"] = "financial_statement"
    company_name: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    currency: str = "SAR"
    balance_sheet: BalanceSheet = Field(default_factory=BalanceSheet)
    income_statement: IncomeStatement = Field(default_factory=IncomeStatement)
    ratios: FinancialRatios = Field(default_factory=FinancialRatios)
    flags: list[str] = Field(default_factory=list)
    meta: ExtractionMeta


# ============================================================
# pos_data
# ============================================================

class POSDaily(BaseModel):
    date: str                # ISO yyyy-mm-dd
    revenue_sar: float
    txn_count: int
    avg_ticket_sar: float


class POSAggregates(BaseModel):
    daily_revenue_avg_sar: float | None = None
    monthly_revenue_est_sar: float | None = None
    avg_ticket_sar: float | None = None
    peak_hours: list[str] = Field(default_factory=list)
    seasonality: Literal["weekend_heavy", "weekday_heavy", "flat"] | None = None
    void_rate: float | None = None
    refund_rate: float | None = None
    cash_card_mix: dict[str, float] | None = None   # {"cash": 0.18, "card": 0.82}
    trend_90d: Literal["up", "slightly_up", "stable", "slightly_down", "down"] | None = None


class POSReport(BaseModel):
    doc_type: Literal["pos_data"] = "pos_data"
    merchant_hint: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    currency: str = "SAR"
    daily: list[POSDaily] = Field(default_factory=list)
    aggregates: POSAggregates = Field(default_factory=POSAggregates)
    flags: list[str] = Field(default_factory=list)
    meta: ExtractionMeta


# ============================================================
# invoice
# ============================================================

class InvoiceLine(BaseModel):
    description: str
    quantity: float
    unit_price_sar: float
    total_sar: float


class InvoiceReport(BaseModel):
    doc_type: Literal["invoice"] = "invoice"
    vendor_name: str | None = None
    vendor_vat: str | None = None
    invoice_number: str | None = None
    issue_date: str | None = None
    currency: str = "SAR"
    line_items: list[InvoiceLine] = Field(default_factory=list)
    subtotal_sar: float | None = None
    vat_sar: float | None = None
    total_sar: float | None = None
    item_category: str | None = None
    matches_requested_amount: bool | None = None
    fraud_flags: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    meta: ExtractionMeta

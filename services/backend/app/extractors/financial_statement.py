"""Financial statement extractor (balance sheet + income statement)."""
from __future__ import annotations

from ..schemas.documents import FinancialStatementReport
from ._common import extract_with_schema, pdf_text_block

SYSTEM_PROMPT = """You extract structured data from a KSA company's financial
statements PDF (balance sheet + income statement) for a lease-to-own
underwriting decision.

Produce JSON matching the FinancialStatementReport schema.

Rules:
- Amounts in SAR. Strip currency and thousands separators.
- Populate source_pages on balance_sheet and income_statement with the
  1-indexed pages those sections appear on.
- Compute ratios from the extracted values (do not trust any "ratios" section
  in the PDF unless values are consistent):
    - current_ratio = current_assets / current_liabilities
    - debt_to_equity = total_liabilities / equity
    - gross_margin = (revenue - cogs) / revenue
    - net_margin = net_profit / revenue
- If a section (balance_sheet or income_statement) is missing, leave its fields
  null and add to meta.low_confidence_fields.
- If the source is clearly NOT a financial statement, set confidence=0 and add
  "not_a_financial_statement" to meta.extraction_notes.
"""


async def extract_financial_statement(
    *,
    pdf_bytes: bytes,
    filename: str,
    loan_id: str,
    document_id: str | None = None,
) -> FinancialStatementReport:
    text = pdf_text_block(pdf_bytes)
    return await extract_with_schema(
        model_cls=FinancialStatementReport,
        loan_id=loan_id,
        document_id=document_id,
        stage="extract_financial_statement",
        system_prompt=SYSTEM_PROMPT,
        user_payload=text,
        filename=filename,
    )

"""Bank statement extractor."""
from __future__ import annotations

from ..schemas.documents import BankStatementReport
from ._common import extract_with_schema, pdf_text_block

SYSTEM_PROMPT = """You extract structured data from a KSA bank statement PDF for
a lease-to-own underwriting decision.

Produce JSON matching the BankStatementReport schema.

Rules:
- Every numeric field that can be cross-referenced with a specific PDF page
  should include source_pages (1-indexed).
- Use SAR amounts. Strip currency symbols and thousands separators.
- For aggregates (avg/volatility/trend), COMPUTE from the monthly data:
    - monthly_revenue_avg_sar = mean(monthly.revenue_sar)
    - monthly_expenses_avg_sar = mean(monthly.expenses_sar)
    - monthly_net_avg_sar = mean(monthly.net_sar)
    - volatility = std(monthly.net_sar) / |mean(monthly.net_sar)|  (0-1 ish)
    - trend: "up" if second-half mean > first-half mean by >5%, "down" if <-5%, else "stable"
- If a field is missing or the PDF has partial data, return null for that field and
  list the field name in meta.low_confidence_fields.
- If the source document is clearly NOT a bank statement, set confidence=0,
  add "not_a_bank_statement" to meta.extraction_notes, and leave numeric fields null.
"""


async def extract_bank_statement(
    *,
    pdf_bytes: bytes,
    filename: str,
    loan_id: str,
    document_id: str | None = None,
) -> BankStatementReport:
    text = pdf_text_block(pdf_bytes)
    return await extract_with_schema(
        model_cls=BankStatementReport,
        loan_id=loan_id,
        document_id=document_id,
        stage="extract_bank_statement",
        system_prompt=SYSTEM_PROMPT,
        user_payload=text,
        filename=filename,
    )

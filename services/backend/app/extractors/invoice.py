"""Invoice extractor — for the item being financed."""
from __future__ import annotations

from ..schemas.documents import InvoiceReport
from ._common import extract_with_schema, pdf_text_block

SYSTEM_PROMPT = """You extract structured data from a KSA vendor tax invoice
PDF for a lease-to-own application. The invoice is for the equipment or item
the merchant is asking to finance.

Produce JSON matching the InvoiceReport schema.

Rules:
- Amounts in SAR. 15% VAT is standard KSA; verify subtotal + vat ≈ total.
- item_category: classify the main item into one of:
  "coffee_equipment", "commercial_cooking", "refrigeration", "pos_hardware",
  "furniture_fixtures", "general_fnb_equipment", "other".
- matches_requested_amount: if the user_payload includes a "requested_amount",
  set True when |total - requested_amount| / requested_amount < 0.10, else False.
  If requested_amount isn't provided, leave null.
- fraud_flags: include any of these when warranted:
    "subtotal_vat_total_mismatch" — the totals don't add up
    "vendor_vat_missing" — no VAT number on the invoice
    "date_in_future" — issue_date in the future
    "unusual_line_items" — generic / vague / inflated-looking descriptions
"""


async def extract_invoice(
    *,
    pdf_bytes: bytes,
    filename: str,
    loan_id: str,
    document_id: str | None = None,
    requested_amount_sar: float | None = None,
) -> InvoiceReport:
    text = pdf_text_block(pdf_bytes)
    if requested_amount_sar is not None:
        text = f"requested_amount: SAR {requested_amount_sar:,.2f}\n\n" + text
    return await extract_with_schema(
        model_cls=InvoiceReport,
        loan_id=loan_id,
        document_id=document_id,
        stage="extract_invoice",
        system_prompt=SYSTEM_PROMPT,
        user_payload=text,
        filename=filename,
    )

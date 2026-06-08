"""Per-document extractors.

Each extractor takes (bytes, filename, loan_id, document_id) and returns
a Pydantic report model matching the document's shared schema.

Extractors use fitz (PyMuPDF) for PDFs and pandas for CSVs, then call
MiniMax with the schema to populate fields. Every LLM call is traced
via ai_traces.
"""
from __future__ import annotations

from typing import Any

from ..schemas.documents import (
    BankStatementReport,
    FinancialStatementReport,
    InvoiceReport,
    POSReport,
)
from .bank_statement import extract_bank_statement
from .financial_statement import extract_financial_statement
from .invoice import extract_invoice
from .pos_data import extract_pos_data

# Dispatch by doc_type
REGISTRY: dict[str, Any] = {
    "bank_statement":      extract_bank_statement,
    "financial_statement": extract_financial_statement,
    "pos_data":            extract_pos_data,
    "invoice":             extract_invoice,
}

__all__ = [
    "REGISTRY",
    "extract_bank_statement",
    "extract_financial_statement",
    "extract_pos_data",
    "extract_invoice",
    "BankStatementReport",
    "FinancialStatementReport",
    "POSReport",
    "InvoiceReport",
]

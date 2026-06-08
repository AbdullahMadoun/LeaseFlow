"""Fake document generators. Produce realistic fixtures we can feed to
extractors during development, demos, and end-to-end tests.

Every generator returns (bytes, report_instance) where `report_instance` is
the same Pydantic model the extractor outputs. Tests can assert the
extractor round-trips to something close to the original.
"""
from __future__ import annotations

from .bank_statement import generate_bank_statement
from .financial_statement import generate_financial_statement
from .invoice import generate_invoice
from .pos_data import generate_pos_data

__all__ = [
    "generate_bank_statement",
    "generate_financial_statement",
    "generate_pos_data",
    "generate_invoice",
]

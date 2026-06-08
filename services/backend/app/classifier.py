"""Fast keyword-heuristic document classifier.

Given a Storage path to a just-uploaded file, peeks inside with fitz (for
PDFs) or pandas (for CSVs) and returns a predicted doc_type + confidence.
Used by the frontend completeness UX before the documents row is created.

Not a replacement for the extractors — those run later during Phase A and
can detect misclassification (system prompt tells the LLM to set
confidence=0 if the doc doesn't match its expected type). This is just
fast UX scaffolding.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Any

import fitz
import pandas as pd

log = logging.getLogger(__name__)

# Doc types we know how to classify
DOC_TYPES = ("bank_statement", "financial_statement", "invoice", "pos_data")

# --- Keyword weights per doc type. Scores > CONF_MIN become the predicted type.
# Arabic variants included because KSA merchants will upload mixed-language docs.
KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "bank_statement": [
        ("opening balance",             3),
        ("closing balance",             3),
        ("statement of account",        3),
        ("account statement",           3),
        ("monthly statement",           2),
        ("iban",                        2),
        ("transaction date",            2),
        ("beneficiary",                 1),
        ("running balance",             3),
        ("available balance",           2),
        # KSA bank names
        ("al rajhi",                    3),
        ("saudi national bank",         3),
        ("alinma bank",                 3),
        ("riyad bank",                  3),
        ("banque saudi fransi",         3),
        ("arab national bank",          3),
        ("bank albilad",                3),
        ("bank aljazira",               3),
        # Arabic
        ("كشف حساب",                     3),
        ("الرصيد الافتتاحي",             3),
        ("الرصيد الختامي",               3),
    ],
    "financial_statement": [
        ("balance sheet",               4),
        ("statement of financial position", 4),
        ("income statement",            4),
        ("profit and loss",             3),
        ("statement of profit or loss", 3),
        ("total assets",                3),
        ("total liabilities",           3),
        ("shareholders equity",         2),
        ("retained earnings",           2),
        ("cost of goods sold",          2),
        ("operating expenses",          2),
        ("net profit",                  2),
        ("gross margin",                2),
        ("current ratio",               2),
        ("debt-to-equity",              2),
        ("non-current assets",          2),
        # Arabic
        ("قائمة المركز المالي",         3),
        ("قائمة الدخل",                 3),
        ("إجمالي الأصول",               3),
    ],
    "invoice": [
        ("tax invoice",                 4),
        ("invoice number",              3),
        ("invoice no",                  2),
        ("vat",                         2),
        ("vat registration",            2),
        ("vat no",                      1),
        ("subtotal",                    2),
        ("invoice date",                2),
        ("bill to",                     2),
        ("quantity",                    1),
        ("unit price",                  2),
        # Arabic
        ("فاتورة ضريبية",                4),
        ("فاتورة",                       3),
        ("رقم الضريبي",                  2),
        ("الرقم الضريبي",                2),
    ],
}

# CSV headers that strongly suggest POS transaction data
POS_CSV_HEADERS = {
    "transaction_id", "txn_id", "timestamp", "ticket_total", "ticket",
    "payment_method", "void", "refund", "staff", "item", "branch",
    "amount", "total",
}

CONF_MIN = 0.55     # below this → "unknown"
STRONG_HIT = 0.80   # above this → very high confidence


def classify_pdf_bytes(pdf_bytes: bytes) -> dict[str, Any]:
    """Run fitz over the first 3 pages, score keywords, pick the winning
    doc_type. Returns dict with doc_type, confidence, signals, snippet.
    """
    text = _first_pages_text(pdf_bytes, max_pages=3)
    lowered = text.lower()

    # Accumulate per-type scores
    scores: dict[str, int] = {k: 0 for k in KEYWORDS}
    signals: dict[str, list[str]] = {k: [] for k in KEYWORDS}
    for dt, kws in KEYWORDS.items():
        for kw, w in kws:
            if kw.lower() in lowered:
                scores[dt] += w
                signals[dt].append(kw)

    # Transaction-line heuristic boost for bank_statement:
    # many rows of DATE + AMOUNT style content
    date_amt_hits = _count_date_amount_lines(text)
    if date_amt_hits >= 5:
        scores["bank_statement"] += min(6, date_amt_hits // 2)
        signals["bank_statement"].append(f"transaction-like-lines({date_amt_hits})")

    # Heuristic: very short PDF (1-2 pages) with "VAT" + "subtotal/total" skews invoice
    page_count = _count_pages(pdf_bytes)
    if page_count <= 2 and "vat" in lowered and ("subtotal" in lowered or "total" in lowered):
        scores["invoice"] += 3
        signals["invoice"].append("short_pdf_with_vat_totals")

    best_type, best_score = max(scores.items(), key=lambda kv: kv[1])
    total = sum(scores.values()) or 1
    confidence = round(best_score / total, 3)

    # Confidence should also reflect absolute hit strength — a type with
    # score 20 on a doc where others scored 2 each is stronger than one
    # with 20 where others scored 18 each. Normalise to [0, 1].
    if best_score < 4:
        confidence = 0.0
        best_type = "unknown"

    snippet = text[:400].strip()
    return {
        "doc_type": best_type if confidence >= CONF_MIN else "unknown",
        "confidence": min(1.0, confidence),
        "raw_scores": scores,
        "signals": {best_type: signals.get(best_type, [])} if best_type != "unknown" else signals,
        "page_count": page_count,
        "snippet": snippet,
    }


def classify_csv_bytes(csv_bytes: bytes) -> dict[str, Any]:
    """Sniff CSV headers. POS data is the only CSV we expect."""
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes), nrows=5)
    except Exception as e:  # noqa: BLE001
        return {"doc_type": "unknown", "confidence": 0.0,
                "signals": {}, "snippet": f"csv parse error: {e}"[:200]}
    headers = {c.strip().lower() for c in df.columns}
    overlap = headers & POS_CSV_HEADERS
    confidence = min(1.0, len(overlap) / 4)  # 4 matching headers = 1.0
    doc_type = "pos_data" if confidence >= CONF_MIN else "unknown"
    return {
        "doc_type": doc_type,
        "confidence": round(confidence, 3),
        "signals": {doc_type: sorted(overlap)} if doc_type != "unknown" else {},
        "headers": sorted(headers)[:20],
        "row_preview": df.head(3).to_dict(orient="records"),
    }


def classify_bytes(content: bytes, filename: str) -> dict[str, Any]:
    """Dispatch on file extension / magic."""
    lower = filename.lower()
    if lower.endswith(".csv") or lower.endswith(".tsv"):
        return classify_csv_bytes(content)
    if lower.endswith(".pdf") or content[:4] == b"%PDF":
        return classify_pdf_bytes(content)
    # Excel handling could go here; for now treat .xlsx as unknown
    return {"doc_type": "unknown", "confidence": 0.0, "signals": {},
            "snippet": f"unsupported file type: {filename}"}


# --- helpers -----------------------------------------------------------------

def _first_pages_text(pdf_bytes: bytes, *, max_pages: int = 3) -> str:
    parts = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            parts.append(page.get_text("text"))
    return "\n".join(parts)


def _count_pages(pdf_bytes: bytes) -> int:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return doc.page_count


# A DATE AMOUNT line pattern: something that looks like a date (any common
# format) followed by a currency-ish amount somewhere in the same line.
_DATE_RE = re.compile(
    r"(?:(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})"
    r"|(?:\d{2,4}[-/.]\d{1,2}[-/.]\d{1,2})"
    r"|(?:\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}))",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r"\b\d{1,3}(?:[,\s]\d{3})*(?:\.\d{1,2})\b")


def _count_date_amount_lines(text: str) -> int:
    n = 0
    for line in text.splitlines():
        if _DATE_RE.search(line) and _AMOUNT_RE.search(line):
            n += 1
    return n

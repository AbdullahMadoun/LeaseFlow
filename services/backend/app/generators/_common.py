"""Shared helpers for document generators."""
from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta


def seed_rng(seed_str: str, salt: str = "") -> random.Random:
    """Derive a deterministic RNG from any string seed."""
    h = hashlib.sha256((salt + ":" + seed_str).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def sar(amount: float) -> str:
    """Format a number as SAR currency with two decimals and thousands separator."""
    return f"SAR {amount:,.2f}"


def daterange_months(end: date, months: int) -> list[date]:
    """Return `months` first-of-month dates ending at `end`'s month."""
    out: list[date] = []
    y, m = end.year, end.month
    for _ in range(months):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


BANK_NAMES = ["Al Rajhi Bank", "Saudi National Bank", "Riyad Bank",
              "Banque Saudi Fransi", "Arab National Bank", "Alinma Bank"]

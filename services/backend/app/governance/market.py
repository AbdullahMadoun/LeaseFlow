"""Market risk status — STUB.

Replace with a live feed when available: GASTAT F&B indicators, import cost
indices, or a commercial data provider.
"""
from __future__ import annotations

# STUB — replace with live KSA F&B market data feed
MARKET_DATA: dict = {
    "market_status": "medium_risk",
    "market_notes": (
        "KSA F&B sector shows moderate growth; Vision 2030 dining expansion "
        "offset by rising food import costs in Q1 2026."
    ),
    "last_updated": "2026-04-01",
}


def current() -> dict:
    return dict(MARKET_DATA)

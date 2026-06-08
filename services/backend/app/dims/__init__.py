"""Dimension runners. Each dim produces a DimensionOutput."""
from __future__ import annotations

from typing import Awaitable, Callable

from ..schemas import DimensionName, DimensionOutput
from . import financial, industry, pos, sentiment, simah

DimRunner = Callable[[dict], Awaitable[DimensionOutput]]

REGISTRY: dict[DimensionName, DimRunner] = {
    "pos":            pos.run,
    "financial_docs": financial.run,
    "simah":          simah.run,
    "sentiment":      sentiment.run,
    "industry":       industry.run,
}

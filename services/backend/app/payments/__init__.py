"""Payment + repayment modules.

stream      — Stream App v2 client (consumers, products, subscriptions)
schedule    — repayment schedule + Stream subscription installation
"""
from __future__ import annotations

from .schedule import (
    compute_schedule,
    install_schedule_for_loan,
    map_frequency_to_stream,
)
from .stream import (
    StreamAPIError,
    StreamClient,
    StreamConsumer,
    StreamProduct,
    StreamSubscription,
    get_stream_client,
)

__all__ = [
    "StreamAPIError",
    "StreamClient",
    "StreamConsumer",
    "StreamProduct",
    "StreamSubscription",
    "get_stream_client",
    "compute_schedule",
    "install_schedule_for_loan",
    "map_frequency_to_stream",
]

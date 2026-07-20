from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from darwin.domain.enums import Exchange
from darwin.domain.orderbook import OrderBookDelta, OrderBookSnapshot

NormalizedEventType = Literal[
    "market_metadata",
    "orderbook_snapshot",
    "orderbook_delta",
    "public_trade",
    "market_status",
    "heartbeat",
    "reconnect",
    "sequence_gap",
    "snapshot_recovery",
    "timer",
    "paper_order",
    "paper_fill",
    "risk",
    "health",
    "shutdown",
]


@dataclass(frozen=True)
class NormalizedEvent:
    event_type: NormalizedEventType
    exchange: Exchange
    market_id: str | None
    exchange_ts: datetime | None
    received_ts: datetime
    sequence: int | None
    event_id: str
    connection_id: str
    correlation_id: str
    counter: int
    payload: dict[str, Any]
    snapshot: OrderBookSnapshot | None = None
    delta: OrderBookDelta | None = None

    @property
    def sort_key(self) -> tuple[datetime, int, datetime, int]:
        exchange_ts = self.exchange_ts or self.received_ts
        sequence = self.sequence if self.sequence is not None else -1
        return (exchange_ts, sequence, self.received_ts, self.counter)

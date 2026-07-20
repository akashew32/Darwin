from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from darwin.domain.enums import BookSide, Exchange, MarketStatus, OutcomeSide
from darwin.domain.orderbook import OrderBookDelta, OrderBookSnapshot, PriceLevel

BacktestEventType = Literal[
    "orderbook_snapshot",
    "orderbook_delta",
    "trade",
    "market_status",
    "timer",
    "market_close",
    "settlement",
]


@dataclass(frozen=True)
class MarketDataEvent:
    snapshot: OrderBookSnapshot


@dataclass(frozen=True)
class BacktestEvent:
    event_type: BacktestEventType
    market_id: str
    exchange_ts: datetime
    received_ts: datetime
    sequence: int | None
    input_index: int
    payload: dict[str, Any]

    @property
    def sort_key(self) -> tuple[datetime, datetime, int, int]:
        return (
            self.exchange_ts,
            self.received_ts,
            self.sequence if self.sequence is not None else 0,
            self.input_index,
        )


def parse_event(raw: dict[str, Any], input_index: int) -> BacktestEvent:
    event_type = raw["event_type"]
    market_id = str(raw["market_id"])
    exchange_ts = _parse_ts(raw.get("exchange_ts") or raw["received_ts"])
    received_ts = _parse_ts(raw["received_ts"])
    return BacktestEvent(
        event_type=event_type,
        market_id=market_id,
        exchange_ts=exchange_ts,
        received_ts=received_ts,
        sequence=raw.get("sequence"),
        input_index=input_index,
        payload=raw,
    )


def snapshot_from_event(event: BacktestEvent) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        exchange=Exchange.KALSHI,
        market_id=event.market_id,
        bids=tuple(
            PriceLevel(price=Decimal(str(price)), quantity=int(quantity))
            for price, quantity in event.payload.get("bids", [])
        ),
        asks=tuple(
            PriceLevel(price=Decimal(str(price)), quantity=int(quantity))
            for price, quantity in event.payload.get("asks", [])
        ),
        sequence=event.sequence,
        exchange_ts=event.exchange_ts,
        received_ts=event.received_ts,
    )


def delta_from_event(event: BacktestEvent) -> OrderBookDelta:
    return OrderBookDelta(
        exchange=Exchange.KALSHI,
        market_id=event.market_id,
        side=BookSide(event.payload["side"]),
        outcome=OutcomeSide.YES,
        price=Decimal(str(event.payload["price"])),
        delta_quantity=int(event.payload.get("delta_quantity", 0)),
        absolute_quantity=event.payload.get("absolute_quantity"),
        sequence=event.sequence,
        exchange_ts=event.exchange_ts,
        received_ts=event.received_ts,
    )


def status_from_event(event: BacktestEvent) -> MarketStatus:
    return MarketStatus(event.payload.get("status", MarketStatus.OPEN))


def read_events(path: str) -> list[BacktestEvent]:
    import json
    from pathlib import Path

    events: list[BacktestEvent] = []
    with Path(path).open() as handle:
        for index, line in enumerate(handle):
            if line.strip():
                raw = json.loads(line)
                events.append(parse_event(raw, index))
    return sorted(events, key=lambda event: event.sort_key)


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)

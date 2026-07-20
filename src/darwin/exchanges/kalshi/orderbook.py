from dataclasses import dataclass, field
from decimal import Decimal

from darwin.domain.enums import BookSide
from darwin.domain.orderbook import OrderBookDelta, OrderBookSnapshot, PriceLevel
from darwin.exchanges.kalshi.exceptions import KalshiSequenceGap


@dataclass
class LocalOrderBook:
    snapshot: OrderBookSnapshot | None = None
    bids: dict[Decimal, int] = field(default_factory=dict)
    asks: dict[Decimal, int] = field(default_factory=dict)
    sequence: int | None = None

    def apply_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        self.snapshot = snapshot
        self.bids = {level.price: level.quantity for level in snapshot.bids if level.quantity > 0}
        self.asks = {level.price: level.quantity for level in snapshot.asks if level.quantity > 0}
        self.sequence = snapshot.sequence

    def apply_delta(self, delta: OrderBookDelta) -> OrderBookSnapshot:
        if self.snapshot is None:
            raise ValueError("cannot apply delta before snapshot")
        if (
            self.sequence is not None
            and delta.sequence is not None
            and delta.sequence <= self.sequence
        ):
            return self.current_snapshot(received_sequence=self.sequence)
        if (
            self.sequence is not None
            and delta.sequence is not None
            and delta.sequence != self.sequence + 1
        ):
            raise KalshiSequenceGap(f"expected sequence {self.sequence + 1}, got {delta.sequence}")
        book = self.bids if delta.side == BookSide.BID else self.asks
        quantity = delta.absolute_quantity
        if quantity is None:
            quantity = book.get(delta.price, 0) + delta.delta_quantity
        if quantity < 0:
            raise ValueError("delta would create negative depth")
        if quantity == 0:
            book.pop(delta.price, None)
        else:
            book[delta.price] = quantity
        self.sequence = delta.sequence if delta.sequence is not None else self.sequence
        return self.current_snapshot(received_sequence=self.sequence)

    def current_snapshot(self, received_sequence: int | None = None) -> OrderBookSnapshot:
        if self.snapshot is None:
            raise ValueError("book has no snapshot")
        return OrderBookSnapshot(
            exchange=self.snapshot.exchange,
            market_id=self.snapshot.market_id,
            outcome=self.snapshot.outcome,
            bids=tuple(
                PriceLevel(price=price, quantity=quantity)
                for price, quantity in sorted(self.bids.items(), reverse=True)
            ),
            asks=tuple(
                PriceLevel(price=price, quantity=quantity)
                for price, quantity in sorted(self.asks.items())
            ),
            sequence=received_sequence,
            exchange_ts=self.snapshot.exchange_ts,
            received_ts=self.snapshot.received_ts,
        )

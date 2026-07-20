from dataclasses import dataclass

from darwin.domain.orderbook import OrderBookSnapshot


@dataclass(frozen=True)
class MarketDataEvent:
    snapshot: OrderBookSnapshot

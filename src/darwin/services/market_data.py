from collections.abc import AsyncIterator
from typing import Protocol

from darwin.data.events import NormalizedEvent
from darwin.domain.market import Market
from darwin.domain.orderbook import OrderBookSnapshot


class MarketDataProvider(Protocol):
    async def list_markets(self, status: str | None = None) -> list[Market]: ...

    async def get_orderbook(self, market_id: str) -> OrderBookSnapshot: ...

    def stream_market_events(self, market_ids: list[str]) -> AsyncIterator[NormalizedEvent]: ...

    async def close(self) -> None: ...

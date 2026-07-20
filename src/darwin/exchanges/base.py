from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from darwin.domain.fill import Fill
from darwin.domain.market import Event, Market
from darwin.domain.order import Order, OrderRequest
from darwin.domain.orderbook import OrderBookDelta, OrderBookSnapshot


class ExchangeClient(ABC):
    """Exchange-independent async adapter interface."""

    @abstractmethod
    async def list_events(self) -> list[Event]: ...

    @abstractmethod
    async def list_markets(self, status: str | None = None) -> list[Market]: ...

    @abstractmethod
    async def get_orderbook(self, market_id: str) -> OrderBookSnapshot: ...

    @abstractmethod
    def stream_orderbook(self, market_ids: list[str]) -> AsyncIterator[OrderBookDelta]: ...

    @abstractmethod
    async def submit_order(self, request: OrderRequest) -> Order: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> Order: ...

    @abstractmethod
    async def list_fills(self) -> list[Fill]: ...

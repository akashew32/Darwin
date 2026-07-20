from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

from darwin.config import ExchangeConfig
from darwin.domain.enums import OrderStatus
from darwin.domain.fill import Fill
from darwin.domain.market import Event, Market
from darwin.domain.order import Order, OrderRequest
from darwin.domain.orderbook import OrderBookDelta, OrderBookSnapshot
from darwin.exchanges.base import ExchangeClient
from darwin.exchanges.kalshi.mapper import (
    map_delta,
    map_event,
    map_fill,
    map_market,
    map_orderbook,
    probability_to_cents,
)
from darwin.exchanges.kalshi.rest import KalshiRestClient
from darwin.exchanges.kalshi.websocket import KalshiWebSocketClient


class KalshiClient(ExchangeClient):
    def __init__(self, rest: KalshiRestClient, ws: KalshiWebSocketClient) -> None:
        self.rest = rest
        self.ws = ws

    @classmethod
    def from_config(cls, config: ExchangeConfig) -> "KalshiClient":
        return cls(KalshiRestClient(config), KalshiWebSocketClient(config))

    async def list_events(self) -> list[Event]:
        payload = await self.rest.get_events()
        return [map_event(item) for item in payload.get("events", [])]

    async def list_markets(self, status: str | None = None) -> list[Market]:
        payload = await self.rest.get_markets(status=status)
        return [map_market(item) for item in payload.get("markets", [])]

    async def get_orderbook(self, market_id: str) -> OrderBookSnapshot:
        payload = await self.rest.get_orderbook(market_id)
        return map_orderbook(market_id, payload, datetime.now(UTC))

    async def stream_orderbook(self, market_ids: list[str]) -> AsyncIterator[OrderBookDelta]:
        async for raw in self.ws.connect_and_subscribe(["orderbook_delta"], market_ids):
            yield map_delta(raw, datetime.now(UTC))

    async def submit_order(self, request: OrderRequest) -> Order:
        payload = {
            "ticker": request.market_id,
            "client_order_id": request.client_order_id,
            "side": "bid" if request.intent.value == "buy" else "ask",
            "type": "limit",
            "action": request.intent.value,
            "yes_no": request.outcome.value,
            "price": str(Decimal(probability_to_cents(request.limit_price)) / Decimal("100")),
            "count": str(request.quantity),
            "post_only": request.post_only,
        }
        response = await self.rest.submit_order(payload)
        raw = response.get("order", response)
        return Order(
            request=request,
            status=OrderStatus.SUBMITTED,
            remaining_quantity=request.quantity,
            exchange_order_id=str(raw.get("order_id") or raw.get("id") or ""),
            created_ts=request.created_ts,
            updated_ts=datetime.now(UTC),
        )

    async def cancel_order(self, order_id: str) -> Order:
        raise NotImplementedError("cancel_order requires the original request in the order manager")

    async def list_fills(self) -> list[Fill]:
        payload = await self.rest.get_fills()
        return [map_fill(item, datetime.now(UTC)) for item in payload.get("fills", [])]

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from darwin.data.events import NormalizedEvent
from darwin.domain.enums import BookSide, Exchange, MarketStatus, OutcomeSide
from darwin.domain.market import Market
from darwin.domain.orderbook import OrderBookDelta, OrderBookSnapshot, PriceLevel
from darwin.services.market_data import MarketDataProvider


class MockMarketDataProvider(MarketDataProvider):
    """Deterministic read-only exchange used for live-paper tests and smoke runs."""

    def __init__(self) -> None:
        self.execution_endpoint_calls = 0
        self.closed = False
        self.start = datetime(2026, 1, 1, tzinfo=UTC)

    async def list_markets(self, status: str | None = None) -> list[Market]:
        return [
            Market(
                exchange=Exchange.KALSHI,
                market_id="KXTEST-A",
                event_id="MOCK",
                title="Mock A",
                status=MarketStatus.OPEN,
                close_time=self.start + timedelta(hours=1),
            ),
            Market(
                exchange=Exchange.KALSHI,
                market_id="KXTEST-B",
                event_id="MOCK",
                title="Mock B",
                status=MarketStatus.OPEN,
                close_time=self.start + timedelta(hours=1),
            ),
        ]

    async def get_orderbook(self, market_id: str) -> OrderBookSnapshot:
        return self._snapshot(market_id, 1, Decimal("0.48"), Decimal("0.50"), ask_qty=4)

    async def close(self) -> None:
        self.closed = True

    async def forbidden_submit_order(self) -> None:
        self.execution_endpoint_calls += 1
        raise AssertionError("paper-live must never call exchange execution endpoints")

    async def stream_market_events(self, market_ids: list[str]) -> AsyncIterator[NormalizedEvent]:
        counter = 0
        for market_id in market_ids:
            counter += 1
            snapshot = await self.get_orderbook(market_id)
            yield self._event("orderbook_snapshot", market_id, counter, 1, snapshot=snapshot)
        counter += 1
        yield self._event("heartbeat", None, counter, None)
        counter += 1
        yield self._event(
            "orderbook_delta",
            market_ids[0],
            counter,
            2,
            delta=OrderBookDelta(
                exchange=Exchange.KALSHI,
                market_id=market_ids[0],
                side=BookSide.ASK,
                outcome=OutcomeSide.YES,
                price=Decimal("0.50"),
                delta_quantity=-2,
                sequence=2,
                received_ts=self.start + timedelta(seconds=1),
            ),
            momentum=2.0,
        )
        counter += 1
        yield self._event(
            "orderbook_delta",
            market_ids[0],
            counter,
            4,
            delta=OrderBookDelta(
                exchange=Exchange.KALSHI,
                market_id=market_ids[0],
                side=BookSide.BID,
                outcome=OutcomeSide.YES,
                price=Decimal("0.49"),
                delta_quantity=1,
                sequence=4,
                received_ts=self.start + timedelta(seconds=2),
            ),
            momentum=2.0,
        )
        counter += 1
        recovered = self._snapshot(market_ids[0], 4, Decimal("0.62"), Decimal("0.64"), ask_qty=30)
        yield self._event("snapshot_recovery", market_ids[0], counter, 4, snapshot=recovered)
        counter += 1
        yield self._event("reconnect", None, counter, None)
        counter += 1
        yield self._event(
            "orderbook_snapshot",
            market_ids[1],
            counter,
            2,
            snapshot=self._snapshot(market_ids[1], 2, Decimal("0.40"), Decimal("0.80"), ask_qty=100),
            momentum=3.0,
        )
        counter += 1
        yield self._event(
            "orderbook_snapshot",
            market_ids[0],
            counter,
            5,
            snapshot=self._snapshot(market_ids[0], 5, Decimal("0.62"), Decimal("0.64"), ask_qty=30),
            momentum=-2.0,
        )
        await asyncio.sleep(0)

    def _snapshot(
        self,
        market_id: str,
        sequence: int,
        bid: Decimal,
        ask: Decimal,
        *,
        ask_qty: int,
    ) -> OrderBookSnapshot:
        return OrderBookSnapshot(
            exchange=Exchange.KALSHI,
            market_id=market_id,
            bids=(PriceLevel(price=bid, quantity=100),),
            asks=(PriceLevel(price=ask, quantity=ask_qty), PriceLevel(price=ask + Decimal("0.01"), quantity=4)),
            sequence=sequence,
            received_ts=self.start + timedelta(seconds=sequence),
        )

    def _event(
        self,
        event_type: str,
        market_id: str | None,
        counter: int,
        sequence: int | None,
        *,
        snapshot: OrderBookSnapshot | None = None,
        delta: OrderBookDelta | None = None,
        momentum: float = 0.0,
    ) -> NormalizedEvent:
        return NormalizedEvent(
            event_type=event_type,  # type: ignore[arg-type]
            exchange=Exchange.KALSHI,
            market_id=market_id,
            exchange_ts=self.start + timedelta(seconds=counter),
            received_ts=self.start + timedelta(seconds=counter),
            sequence=sequence,
            event_id=f"mock-{counter}",
            connection_id="mock-connection",
            correlation_id=f"mock-{counter}",
            counter=counter,
            payload={"momentum": momentum},
            snapshot=snapshot,
            delta=delta,
        )

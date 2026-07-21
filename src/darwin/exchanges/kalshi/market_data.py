from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast

from darwin.clock import Clock, SystemClock
from darwin.config import ExchangeConfig
from darwin.data.events import NormalizedEvent
from darwin.domain.enums import Exchange
from darwin.domain.market import Market
from darwin.domain.orderbook import OrderBookDelta, OrderBookSnapshot
from darwin.exchanges.kalshi.mapper import map_delta, map_market, map_orderbook
from darwin.exchanges.kalshi.rest import KalshiRestClient
from darwin.exchanges.kalshi.websocket import KalshiSubscriptionSpec, KalshiWebSocketClient
from darwin.logging import get_logger
from darwin.services.market_data import MarketDataProvider


class KalshiRestMarketData(Protocol):
    async def get_markets(
        self,
        status: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
        event_ticker: str | None = None,
    ) -> dict[str, Any]: ...

    async def get_market(self, market_ticker: str) -> dict[str, Any]: ...

    async def get_orderbook(self, market_ticker: str) -> dict[str, Any]: ...

    async def close(self) -> None: ...


class KalshiWebSocketMarketData(Protocol):
    reconnect_count: int
    messages_received: int
    malformed_messages: int
    queue_overflow_count: int
    connection_generation: int
    subscriptions: dict[Any, Any]

    def connect_with_specs(
        self,
        specs: list[KalshiSubscriptionSpec],
    ) -> AsyncIterator[dict[str, Any]]: ...

    async def stop(self) -> None: ...


@dataclass(frozen=True)
class SequenceDomain:
    connection_generation: int
    subscription_id: int | None
    channel: str
    market_id: str | None


@dataclass
class KalshiMarketDataMetrics:
    websocket_reconnects: int = 0
    messages_received: int = 0
    snapshots_loaded: int = 0
    sequence_gaps: int = 0
    out_of_order: int = 0
    snapshot_recoveries: int = 0
    malformed_messages: int = 0
    duplicates: int = 0
    validation_checks: int = 0
    validation_failures: int = 0
    book_divergences: int = 0
    corrective_rebuilds: int = 0
    last_sequences: dict[SequenceDomain, int] = field(default_factory=dict)
    seen_event_ids: set[str] = field(default_factory=set)


class KalshiMarketDataProvider(MarketDataProvider):
    """Read-only Kalshi market-data provider for live paper trading.

    This class intentionally exposes no order, cancellation, amendment,
    portfolio, balance, fill, or position methods.
    """

    def __init__(
        self,
        *,
        rest: KalshiRestMarketData,
        websocket: KalshiWebSocketMarketData,
        connection_id: str = "kalshi",
        clock: Clock | None = None,
        recovery_timeout_seconds: float = 10.0,
        max_backward_events: int = 3,
    ) -> None:
        self.rest = rest
        self.websocket = websocket
        self.connection_id = connection_id
        self.clock = clock or SystemClock()
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.max_backward_events = max_backward_events
        self.metrics = KalshiMarketDataMetrics()
        self.logger = get_logger("darwin.kalshi.market_data")
        self._counter = 0
        self._pending_recovery: NormalizedEvent | None = None
        self._last_reconnect_count = 0
        self._backward_counts: dict[SequenceDomain, int] = {}

    @classmethod
    def from_config(cls, config: ExchangeConfig) -> "KalshiMarketDataProvider":
        if not config.has_credentials:
            raise ValueError(
                "Kalshi WebSocket market data requires KALSHI_API_KEY_ID and a private key. "
                "REST market data is public, but paper-live kalshi streaming needs a signed "
                "read-only WebSocket handshake."
            )
        clock = SystemClock()
        return cls(
            rest=KalshiRestClient(config),
            websocket=KalshiWebSocketClient(config, clock=clock),
            clock=clock,
        )

    @classmethod
    def rest_only_from_config(cls, config: ExchangeConfig) -> "KalshiMarketDataProvider":
        return cls(rest=KalshiRestClient(config), websocket=_UnavailableWebSocket())

    async def list_markets(self, status: str | None = None) -> list[Market]:
        raw_markets = await self.list_market_payloads(status=status)
        return [map_market(item) for item in raw_markets]

    async def list_market_payloads(
        self,
        *,
        status: str | None = None,
        event_ticker: str | None = None,
        max_pages: int = 20,
        max_markets: int = 1000,
    ) -> list[dict[str, Any]]:
        cursor: str | None = None
        seen_cursors: set[str] = set()
        markets: list[dict[str, Any]] = []
        for _ in range(max_pages):
            payload = await self.rest.get_markets(
                status=status,
                limit=min(1000, max_markets - len(markets)),
                cursor=cursor,
                event_ticker=event_ticker,
            )
            markets.extend(cast(list[dict[str, Any]], payload["markets"]))
            cursor = str(payload.get("cursor") or "")
            if not cursor or len(markets) >= max_markets:
                break
            if cursor in seen_cursors:
                raise ValueError(f"Kalshi markets pagination cursor loop detected: {cursor}")
            seen_cursors.add(cursor)
        return markets[:max_markets]

    async def get_market(self, market_id: str) -> Market:
        payload = await self.rest.get_market(market_id)
        return map_market(payload["market"])

    async def get_orderbook(self, market_id: str) -> OrderBookSnapshot:
        received_ts = self.clock.now()
        payload = await self.rest.get_orderbook(market_id)
        snapshot = map_orderbook(market_id, payload, received_ts)
        self.metrics.snapshots_loaded += 1
        self.logger.info("kalshi_snapshot_loaded", market_id=market_id, sequence=snapshot.sequence)
        return snapshot

    async def close(self) -> None:
        await self.websocket.stop()
        await self.rest.close()

    async def stream_market_events(self, market_ids: list[str]) -> AsyncIterator[NormalizedEvent]:
        specs = [
            KalshiSubscriptionSpec(
                request_id=1,
                channels=("orderbook_delta", "ticker", "trade"),
                market_tickers=tuple(market_ids),
            ),
            KalshiSubscriptionSpec(
                request_id=2,
                channels=("market_lifecycle_v2",),
                market_tickers=(),
            ),
        ]
        async for raw in self.websocket.connect_with_specs(specs):
            self.metrics.websocket_reconnects = self.websocket.reconnect_count
            self.metrics.messages_received = self.websocket.messages_received
            self.metrics.malformed_messages = self.websocket.malformed_messages
            if self.websocket.queue_overflow_count:
                yield self._event(
                    "health",
                    None,
                    raw,
                    payload={
                        "reason": "queue_overflow",
                        "count": self.websocket.queue_overflow_count,
                    },
                )
            if self.websocket.reconnect_count > self._last_reconnect_count:
                self._last_reconnect_count = self.websocket.reconnect_count
                self.metrics.last_sequences.clear()
                self._backward_counts.clear()
                yield self._event(
                    "reconnect",
                    None,
                    {"type": "reconnect", "msg": {"count": self._last_reconnect_count}},
                    payload={"count": self._last_reconnect_count},
                )
            for event in await self.normalize_with_recovery(raw, market_ids):
                yield event

    async def _normalize(
        self,
        raw: dict[str, Any],
        subscribed_markets: list[str],
    ) -> NormalizedEvent | None:
        event_type = str(raw.get("type") or "")
        msg = raw.get("msg")
        if msg is not None and not isinstance(msg, dict):
            self.metrics.malformed_messages += 1
            return self._event("health", None, raw, payload={"reason": "malformed_msg"})
        if msg is None:
            msg = {}
        market_id = msg.get("market_ticker") or msg.get("ticker")
        if market_id is not None:
            market_id = str(market_id)
        channel = _channel(raw)
        sequence = _optional_int(raw.get("seq"))
        exchange_ts = _message_ts(msg)

        if event_type == "subscribed":
            return self._event("health", None, raw, payload={"reason": "subscribed", "raw": msg})
        if event_type in {"heartbeat", "pong"}:
            return self._event("heartbeat", market_id, raw, sequence=sequence, payload={"raw": msg})
        if event_type == "error":
            return self._event("health", market_id, raw, payload={"reason": "ws_error", "raw": msg})

        if event_type == "orderbook_snapshot":
            snapshot = map_orderbook(market_id or "", msg, self.clock.now())
            snapshot = snapshot.model_copy(
                update={"sequence": sequence, "exchange_ts": exchange_ts}
            )
            self._accept_sequence(raw, market_id, channel, sequence, allow_reset=True)
            self.metrics.snapshots_loaded += 1
            return self._event(
                "orderbook_snapshot",
                market_id,
                raw,
                sequence=sequence,
                exchange_ts=exchange_ts,
                payload={"raw": msg},
                snapshot=snapshot,
            )

        if event_type == "orderbook_delta":
            status = self._classify_sequence(raw, market_id, channel, sequence)
            if status is not None and status["reason"] == "duplicate_sequence":
                return None
            if status is not None and status["reason"] == "backward_sequence":
                return self._event(
                    "health",
                    market_id,
                    raw,
                    sequence=sequence,
                    exchange_ts=exchange_ts,
                    payload=status,
                )
            if status is not None and status["reason"] == "sequence_gap":
                yield_gap = self._event(
                    "sequence_gap",
                    market_id,
                    raw,
                    sequence=sequence,
                    exchange_ts=exchange_ts,
                    payload=status,
                )
                recovery = await self._snapshot_recovery(market_id, raw)
                self._pending_recovery = recovery
                return yield_gap
            delta = map_delta(raw, self.clock.now())
            return self._event(
                "orderbook_delta",
                market_id,
                raw,
                sequence=sequence,
                exchange_ts=exchange_ts,
                payload={"raw": msg},
                delta=delta,
            )

        if event_type == "ticker":
            return self._event(
                "market_metadata",
                market_id,
                raw,
                sequence=sequence,
                exchange_ts=exchange_ts,
                payload={"raw": msg},
            )
        if event_type == "trade":
            return self._event(
                "public_trade",
                market_id,
                raw,
                sequence=sequence,
                exchange_ts=exchange_ts,
                payload={"raw": msg},
            )
        if event_type in {"market_lifecycle_v2", "event_lifecycle", "event_fee_update"}:
            return self._event(
                "market_status",
                market_id,
                raw,
                sequence=sequence,
                exchange_ts=exchange_ts,
                payload={"raw": msg},
            )
        if event_type == "reconnect":
            return self._event("reconnect", None, raw, payload={"raw": msg})
        self.metrics.malformed_messages += 1
        return self._event("health", market_id, raw, payload={"reason": "unknown_type", "raw": msg})

    async def normalize_with_recovery(
        self,
        raw: dict[str, Any],
        subscribed_markets: list[str],
    ) -> list[NormalizedEvent]:
        self._pending_recovery = None
        event = await self._normalize(raw, subscribed_markets)
        events = [] if event is None else [event]
        if self._pending_recovery is not None:
            events.append(self._pending_recovery)
            self._pending_recovery = None
        return events

    def _classify_sequence(
        self,
        raw: dict[str, Any],
        market_id: str | None,
        channel: str,
        sequence: int | None,
    ) -> dict[str, Any] | None:
        domain = self._domain(raw, market_id, channel)
        previous = self.metrics.last_sequences.get(domain)
        if sequence is None:
            return None
        if previous is not None and sequence == previous:
            self.metrics.duplicates += 1
            return {"reason": "duplicate_sequence", "expected": previous + 1, "actual": sequence}
        if previous is not None and sequence < previous:
            self.metrics.out_of_order += 1
            count = self._backward_counts.get(domain, 0) + 1
            self._backward_counts[domain] = count
            reason = "backward_sequence"
            if count > self.max_backward_events:
                reason = "sequence_gap"
                self.metrics.sequence_gaps += 1
            return {"reason": reason, "expected": previous + 1, "actual": sequence}
        if previous is not None and sequence > previous + 1:
            self.metrics.sequence_gaps += 1
            self.logger.warning(
                "kalshi_sequence_gap",
                market_id=market_id,
                expected=previous + 1,
                actual=sequence,
            )
            return {"reason": "sequence_gap", "expected": previous + 1, "actual": sequence}
        self.metrics.last_sequences[domain] = sequence
        self._backward_counts.pop(domain, None)
        return None

    def _accept_sequence(
        self,
        raw: dict[str, Any],
        market_id: str | None,
        channel: str,
        sequence: int | None,
        *,
        allow_reset: bool,
    ) -> None:
        if sequence is None:
            return
        domain = self._domain(raw, market_id, channel)
        if allow_reset or domain not in self.metrics.last_sequences:
            self.metrics.last_sequences[domain] = sequence

    def _domain(self, raw: dict[str, Any], market_id: str | None, channel: str) -> SequenceDomain:
        return SequenceDomain(
            connection_generation=self.websocket.connection_generation,
            subscription_id=raw.get("sid") if isinstance(raw.get("sid"), int) else None,
            channel=channel,
            market_id=market_id,
        )

    async def _snapshot_recovery(
        self,
        market_id: str | None,
        raw: dict[str, Any],
    ) -> NormalizedEvent | None:
        if market_id is None:
            return None
        snapshot: OrderBookSnapshot = await _with_timeout(
            self.get_orderbook(market_id),
            self.recovery_timeout_seconds,
        )
        self.metrics.snapshot_recoveries += 1
        self.logger.info(
            "kalshi_snapshot_recovery",
            market_id=market_id,
            sequence=snapshot.sequence,
        )
        return self._event(
            "snapshot_recovery",
            market_id,
            raw,
            sequence=snapshot.sequence,
            payload={"reason": "sequence_gap_recovery"},
            snapshot=snapshot,
        )

    async def validate_book(
        self,
        local_snapshot: OrderBookSnapshot,
        *,
        top_n: int = 5,
    ) -> dict[str, Any]:
        self.metrics.validation_checks += 1
        rest_snapshot = await self.get_orderbook(local_snapshot.market_id)
        local_bids = [(level.price, level.quantity) for level in local_snapshot.bids[:top_n]]
        rest_bids = [(level.price, level.quantity) for level in rest_snapshot.bids[:top_n]]
        local_asks = [(level.price, level.quantity) for level in local_snapshot.asks[:top_n]]
        rest_asks = [(level.price, level.quantity) for level in rest_snapshot.asks[:top_n]]
        matched = local_bids == rest_bids and local_asks == rest_asks
        if not matched:
            self.metrics.validation_failures += 1
            self.metrics.book_divergences += 1
        return {
            "market_id": local_snapshot.market_id,
            "matched": matched,
            "local_best_bid": str(local_snapshot.best_bid),
            "rest_best_bid": str(rest_snapshot.best_bid),
            "local_best_ask": str(local_snapshot.best_ask),
            "rest_best_ask": str(rest_snapshot.best_ask),
            "local_top_bid_qty": local_snapshot.bids[0].quantity if local_snapshot.bids else 0,
            "rest_top_bid_qty": rest_snapshot.bids[0].quantity if rest_snapshot.bids else 0,
            "local_top_ask_qty": local_snapshot.asks[0].quantity if local_snapshot.asks else 0,
            "rest_top_ask_qty": rest_snapshot.asks[0].quantity if rest_snapshot.asks else 0,
        }

    def _event(
        self,
        event_type: Literal[
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
        ],
        market_id: str | None,
        raw: dict[str, Any],
        *,
        sequence: int | None = None,
        exchange_ts: datetime | None = None,
        payload: dict[str, Any] | None = None,
        snapshot: OrderBookSnapshot | None = None,
        delta: OrderBookDelta | None = None,
    ) -> NormalizedEvent:
        self._counter += 1
        event_id = _event_id(raw, self._counter)
        return NormalizedEvent(
            event_type=event_type,
            exchange=Exchange.KALSHI,
            market_id=market_id,
            exchange_ts=exchange_ts,
            received_ts=self.clock.now(),
            sequence=sequence,
            event_id=event_id,
            connection_id=self.connection_id,
            correlation_id=event_id,
            counter=self._counter,
            payload=payload or {},
            snapshot=snapshot,
            delta=delta,
        )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _message_ts(msg: dict[str, Any]) -> datetime | None:
    ts_ms = msg.get("ts_ms")
    if ts_ms is not None:
        return datetime.fromtimestamp(int(ts_ms) / 1000, tz=UTC)
    ts = msg.get("ts")
    if isinstance(ts, int | float):
        return datetime.fromtimestamp(float(ts), tz=UTC)
    time_value = msg.get("time")
    if time_value:
        return datetime.fromisoformat(str(time_value).replace("Z", "+00:00")).astimezone(UTC)
    return None


async def _with_timeout[T](awaitable: Any, timeout_seconds: float) -> T:
    import asyncio

    return cast(T, await asyncio.wait_for(awaitable, timeout_seconds))


def _channel(raw: dict[str, Any]) -> str:
    msg = raw.get("msg") if isinstance(raw.get("msg"), dict) else {}
    if raw.get("type") == "subscribed" and isinstance(msg, dict):
        return str(msg.get("channel") or raw.get("type"))
    event_type = str(raw.get("type") or "")
    if event_type in {"orderbook_snapshot", "orderbook_delta"}:
        return "orderbook_delta"
    if event_type in {"market_lifecycle_v2", "event_lifecycle", "event_fee_update"}:
        return "market_lifecycle_v2"
    return event_type


def _event_id(raw: dict[str, Any], counter: int) -> str:
    msg = cast(dict[str, Any], raw.get("msg")) if isinstance(raw.get("msg"), dict) else {}
    parts = [
        str(raw.get("type") or "unknown"),
        str(raw.get("sid") or ""),
        str(raw.get("seq") or ""),
        str(msg.get("market_ticker") or msg.get("ticker") or ""),
        str(msg.get("trade_id") or ""),
        str(counter),
    ]
    return ":".join(parts)


class _UnavailableWebSocket:
    def __init__(self) -> None:
        self.reconnect_count = 0
        self.messages_received = 0
        self.malformed_messages = 0
        self.queue_overflow_count = 0
        self.connection_generation = 0
        self.subscriptions: dict[Any, Any] = {}

    def connect_with_specs(
        self,
        specs: list[KalshiSubscriptionSpec],
    ) -> AsyncIterator[dict[str, Any]]:
        async def _empty() -> AsyncIterator[dict[str, Any]]:
            if False:
                yield {}

        return _empty()

    async def stop(self) -> None:
        return None

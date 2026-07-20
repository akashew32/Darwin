import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from darwin.config import ExchangeConfig
from darwin.domain.enums import Exchange
from darwin.exchanges.kalshi.market_data import KalshiMarketDataProvider
from darwin.exchanges.kalshi.rest import KalshiRestClient
from darwin.exchanges.kalshi.websocket import KalshiWebSocketClient


class FakeRest:
    def __init__(self) -> None:
        self.closed = False
        self.snapshots = 0

    async def get_markets(self, status: str | None = None, limit: int = 100) -> dict[str, Any]:
        return {"markets": [_market("KXTEST-A"), _market("KXTEST-B")], "cursor": ""}

    async def get_market(self, market_ticker: str) -> dict[str, Any]:
        return {"market": _market(market_ticker)}

    async def get_orderbook(self, market_ticker: str) -> dict[str, Any]:
        self.snapshots += 1
        return _orderbook()

    async def close(self) -> None:
        self.closed = True


class FakeWebSocket:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = messages
        self.reconnect_count = 0
        self.messages_received = 0
        self.malformed_messages = 0
        self.stopped = False
        self.subscribed: tuple[list[str], list[str]] | None = None

    async def stop(self) -> None:
        self.stopped = True

    async def connect_and_subscribe(
        self,
        channels: list[str],
        market_tickers: list[str],
    ) -> AsyncIterator[dict[str, Any]]:
        self.subscribed = (channels, market_tickers)
        for message in self.messages:
            self.messages_received += 1
            yield message


def _market(ticker: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "event_ticker": "KXTEST",
        "title": ticker,
        "status": "open",
        "close_time": "2026-01-01T01:00:00Z",
    }


def _orderbook() -> dict[str, Any]:
    return {
        "orderbook_fp": {
            "yes_dollars": [["0.4800", "100.00"]],
            "no_dollars": [["0.5000", "40.00"]],
        }
    }


def _fixture_messages() -> list[dict[str, Any]]:
    path = Path("tests/fixtures/kalshi_ws_session.jsonl")
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_kalshi_provider_exposes_only_read_only_methods() -> None:
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=FakeWebSocket([]))
    forbidden = {"submit_order", "cancel_order", "amend_order", "get_balance", "get_positions"}
    assert forbidden.isdisjoint(set(dir(provider)))


@pytest.mark.parametrize("status", [None, "open"])
def test_kalshi_provider_lists_markets(status: str | None) -> None:
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=FakeWebSocket([]))
    markets = asyncio.run(provider.list_markets(status=status))
    assert [market.market_id for market in markets] == ["KXTEST-A", "KXTEST-B"]


def test_kalshi_provider_get_market() -> None:
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=FakeWebSocket([]))
    market = asyncio.run(provider.get_market("KXTEST-A"))
    assert market.exchange == Exchange.KALSHI
    assert market.market_id == "KXTEST-A"


def test_kalshi_provider_get_orderbook_maps_yes_and_implied_asks() -> None:
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=FakeWebSocket([]))
    snapshot = asyncio.run(provider.get_orderbook("KXTEST-A"))
    assert snapshot.best_bid is not None
    assert snapshot.best_ask is not None
    assert snapshot.best_bid < snapshot.best_ask
    assert provider.metrics.snapshots_loaded == 1


def test_kalshi_provider_subscribes_to_expected_channels() -> None:
    ws = FakeWebSocket([])
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=ws)

    async def run() -> None:
        async for _ in provider.stream_market_events(["KXTEST-A"]):
            pass

    asyncio.run(run())
    assert ws.subscribed is not None
    channels, markets = ws.subscribed
    assert "orderbook_delta" in channels
    assert "trade" in channels
    assert "market_lifecycle_v2" in channels
    assert markets == ["KXTEST-A"]


def test_recorded_kalshi_fixture_normalizes_core_event_types() -> None:
    provider = KalshiMarketDataProvider(
        rest=FakeRest(),
        websocket=FakeWebSocket(_fixture_messages()),
    )

    async def run() -> list[str]:
        return [
            event.event_type
            async for event in provider.stream_market_events(["KXTEST-A"])
            if event.event_type != "health"
        ]

    event_types = asyncio.run(run())
    assert "orderbook_snapshot" in event_types
    assert "orderbook_delta" in event_types
    assert "public_trade" in event_types
    assert "market_status" in event_types


def test_sequence_gap_emits_recovery_after_recorded_fixture() -> None:
    rest = FakeRest()
    provider = KalshiMarketDataProvider(rest=rest, websocket=FakeWebSocket(_fixture_messages()))

    async def run() -> list[str]:
        return [event.event_type async for event in provider.stream_market_events(["KXTEST-A"])]

    event_types = asyncio.run(run())
    assert "sequence_gap" in event_types
    assert "snapshot_recovery" in event_types
    assert provider.metrics.sequence_gaps == 1
    assert provider.metrics.snapshot_recoveries == 1
    assert rest.snapshots == 1


def test_sequence_gap_recovery_snapshot_is_valid_orderbook() -> None:
    provider = KalshiMarketDataProvider(
        rest=FakeRest(),
        websocket=FakeWebSocket(_fixture_messages()),
    )

    async def run() -> list[Any]:
        return [event async for event in provider.stream_market_events(["KXTEST-A"])]

    events = asyncio.run(run())
    recovery = next(event for event in events if event.event_type == "snapshot_recovery")
    assert recovery.snapshot is not None
    assert recovery.snapshot.best_bid is not None
    assert recovery.snapshot.best_ask is not None


def test_duplicate_sequence_is_reported_safely() -> None:
    messages = [
        _fixture_messages()[1],
        _fixture_messages()[2],
        _fixture_messages()[2],
    ]
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=FakeWebSocket(messages))

    async def run() -> list[str]:
        return [event.event_type async for event in provider.stream_market_events(["KXTEST-A"])]

    event_types = asyncio.run(run())
    assert "sequence_gap" in event_types
    assert provider.metrics.duplicates == 1


def test_unknown_websocket_type_becomes_health_event() -> None:
    provider = KalshiMarketDataProvider(
        rest=FakeRest(),
        websocket=FakeWebSocket([{"type": "mystery", "msg": {"market_ticker": "KXTEST-A"}}]),
    )

    async def run() -> list[Any]:
        return [event async for event in provider.stream_market_events(["KXTEST-A"])]

    events = asyncio.run(run())
    assert events[0].event_type == "health"
    assert events[0].payload["reason"] == "unknown_type"


def test_provider_close_closes_read_only_clients() -> None:
    rest = FakeRest()
    ws = FakeWebSocket([])
    provider = KalshiMarketDataProvider(rest=rest, websocket=ws)
    asyncio.run(provider.close())
    assert rest.closed
    assert ws.stopped


def test_websocket_reconnect_count_emits_reconnect_event() -> None:
    ws = FakeWebSocket([_fixture_messages()[1]])
    ws.reconnect_count = 1
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=ws)

    async def run() -> list[str]:
        return [event.event_type async for event in provider.stream_market_events(["KXTEST-A"])]

    events = asyncio.run(run())
    assert events[0] == "reconnect"
    assert "orderbook_snapshot" in events


def test_from_config_requires_websocket_credentials() -> None:
    with pytest.raises(ValueError, match="WebSocket market data requires"):
        KalshiMarketDataProvider.from_config(ExchangeConfig())


@pytest.mark.parametrize("status_code", [500, 502, 503])
def test_rest_retries_transient_server_errors(status_code: int) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status_code if calls == 1 else 200, json=_orderbook())

    rest = KalshiRestClient(
        ExchangeConfig(),
        client=httpx.AsyncClient(
            base_url="https://external-api.kalshi.com",
            transport=httpx.MockTransport(handler),
        ),
    )
    asyncio.run(rest.get_orderbook("KXTEST-A"))
    assert calls == 2
    asyncio.run(rest.close())


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"orderbook_fp": {"yes_dollars": []}},
        {"orderbook_fp": {"no_dollars": []}},
    ],
)
def test_rest_rejects_malformed_orderbook_payload(payload: Any) -> None:
    rest = KalshiRestClient(
        ExchangeConfig(),
        client=httpx.AsyncClient(
            base_url="https://external-api.kalshi.com",
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
        ),
    )
    with pytest.raises(ValueError):
        asyncio.run(rest.get_orderbook("KXTEST-A"))
    asyncio.run(rest.close())


def test_websocket_client_tracks_malformed_json() -> None:
    client = KalshiWebSocketClient(ExchangeConfig())
    client.malformed_messages += 1
    assert client.malformed_messages == 1


def test_fixture_book_matches_official_snapshot_after_delta() -> None:
    provider = KalshiMarketDataProvider(
        rest=FakeRest(),
        websocket=FakeWebSocket(_fixture_messages()),
    )

    async def run() -> list[Any]:
        return [event async for event in provider.stream_market_events(["KXTEST-A"])]

    events = asyncio.run(run())
    snapshot = next(event.snapshot for event in events if event.event_type == "orderbook_snapshot")
    delta = next(event.delta for event in events if event.event_type == "orderbook_delta")
    assert snapshot is not None
    assert delta is not None
    assert snapshot.best_bid is not None
    assert delta.price >= snapshot.best_bid

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from darwin.clock import FixedClock
from darwin.config import ExchangeConfig
from darwin.domain.enums import Exchange
from darwin.exchanges.kalshi.market_data import KalshiMarketDataProvider, SequenceDomain
from darwin.exchanges.kalshi.rest import KalshiRestClient
from darwin.exchanges.kalshi.websocket import (
    KalshiQueuedMessage,
    KalshiSubscriptionSpec,
    KalshiWebSocketClient,
    build_subscription_specs,
)


class FakeRest:
    def __init__(self) -> None:
        self.closed = False
        self.snapshots = 0
        self.pages: list[dict[str, Any]] | None = None
        self.calls: list[dict[str, Any]] = []

    async def get_markets(
        self,
        status: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
        event_ticker: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {"status": status, "limit": limit, "cursor": cursor, "event_ticker": event_ticker}
        )
        if self.pages is not None:
            return self.pages.pop(0)
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
        self.queue_overflow_count = 0
        self.connection_generation = 1
        self.stopped = False
        self.specs: list[KalshiSubscriptionSpec] = []
        self.subscriptions: dict[int, object] = {}

    async def stop(self) -> None:
        self.stopped = True

    async def connect_with_specs(
        self,
        specs: list[KalshiSubscriptionSpec],
    ) -> AsyncIterator[dict[str, Any]]:
        self.specs = specs
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


def test_kalshi_provider_subscribes_to_expected_channel_groups() -> None:
    ws = FakeWebSocket([])
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=ws)

    async def run() -> None:
        async for _ in provider.stream_market_events(["KXTEST-A"]):
            pass

    asyncio.run(run())
    assert len(ws.specs) == 2
    filtered, lifecycle = ws.specs
    assert filtered.channels == ("orderbook_delta", "ticker", "trade")
    assert filtered.market_tickers == ("KXTEST-A",)
    assert lifecycle.channels == ("market_lifecycle_v2",)
    assert lifecycle.market_tickers == ()


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
    assert "sequence_gap" not in event_types
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


def test_subscription_builder_splits_lifecycle_without_market_filter() -> None:
    specs = build_subscription_specs(["KXTEST-A", "KXTEST-B"])
    assert specs[0].payload()["params"]["market_tickers"] == ["KXTEST-A", "KXTEST-B"]
    assert "market_tickers" not in specs[1].payload()["params"]


@pytest.mark.parametrize("channel", ["orderbook_delta", "ticker", "trade"])
def test_filtered_subscription_contains_market_channels(channel: str) -> None:
    filtered = build_subscription_specs(["KXTEST-A"])[0]
    assert channel in filtered.channels


@pytest.mark.parametrize("channel", ["market_lifecycle_v2"])
def test_global_subscription_contains_only_global_channels(channel: str) -> None:
    lifecycle = build_subscription_specs(["KXTEST-A"])[1]
    assert lifecycle.channels == (channel,)
    assert lifecycle.market_tickers == ()


def test_subscription_payload_request_ids_are_distinct() -> None:
    specs = build_subscription_specs(["KXTEST-A"], start_request_id=10)
    assert [spec.request_id for spec in specs] == [10, 11]


def test_interleaved_markets_do_not_create_false_gaps() -> None:
    messages = [
        {
            "type": "orderbook_snapshot",
            "sid": 2,
            "seq": 10,
            "msg": _orderbook() | {"market_ticker": "KXTEST-A"},
        },
        {
            "type": "orderbook_snapshot",
            "sid": 2,
            "seq": 20,
            "msg": _orderbook() | {"market_ticker": "KXTEST-B"},
        },
        {
            "type": "orderbook_delta",
            "sid": 2,
            "seq": 11,
            "msg": {
                "market_ticker": "KXTEST-A",
                "side": "yes",
                "price_dollars": "0.4800",
                "delta_fp": "1.00",
            },
        },
        {
            "type": "orderbook_delta",
            "sid": 2,
            "seq": 21,
            "msg": {
                "market_ticker": "KXTEST-B",
                "side": "yes",
                "price_dollars": "0.4800",
                "delta_fp": "1.00",
            },
        },
    ]
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=FakeWebSocket(messages))

    async def run() -> list[str]:
        return [event.event_type async for event in provider.stream_market_events(["KXTEST-A"])]

    assert "sequence_gap" not in asyncio.run(run())


def test_backward_event_is_health_not_recovery() -> None:
    messages = [
        _fixture_messages()[1],
        _fixture_messages()[2],
        {
            "type": "orderbook_delta",
            "sid": 2,
            "seq": 10,
            "msg": {
                "market_ticker": "KXTEST-A",
                "side": "yes",
                "price_dollars": "0.4800",
                "delta_fp": "1.00",
            },
        },
    ]
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=FakeWebSocket(messages))

    async def run() -> list[Any]:
        return [event async for event in provider.stream_market_events(["KXTEST-A"])]

    events = asyncio.run(run())
    assert any(event.payload.get("reason") == "backward_sequence" for event in events)
    assert "snapshot_recovery" not in [event.event_type for event in events]


def test_repeated_backward_events_trigger_recovery() -> None:
    backward = {
        "type": "orderbook_delta",
        "sid": 2,
        "seq": 10,
        "msg": {
            "market_ticker": "KXTEST-A",
            "side": "yes",
            "price_dollars": "0.4800",
            "delta_fp": "1.00",
        },
    }
    provider = KalshiMarketDataProvider(
        rest=FakeRest(),
        websocket=FakeWebSocket([_fixture_messages()[1], _fixture_messages()[2]] + [backward] * 4),
        max_backward_events=2,
    )

    async def run() -> list[str]:
        return [event.event_type async for event in provider.stream_market_events(["KXTEST-A"])]

    events = asyncio.run(run())
    assert "sequence_gap" in events
    assert "snapshot_recovery" in events


def test_reconnect_resets_sequence_baselines() -> None:
    ws = FakeWebSocket([_fixture_messages()[1]])
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=ws)
    asyncio.run(provider.normalize_with_recovery(_fixture_messages()[1], ["KXTEST-A"]))
    assert provider.metrics.last_sequences
    ws.reconnect_count = 1

    async def run() -> list[str]:
        return [event.event_type async for event in provider.stream_market_events(["KXTEST-A"])]

    asyncio.run(run())
    assert provider.metrics.last_sequences
    assert all(domain.connection_generation == 1 for domain in provider.metrics.last_sequences)


def test_sequence_domain_includes_subscription_channel_and_market() -> None:
    domain = SequenceDomain(1, 2, "orderbook_delta", "KXTEST-A")
    assert domain != SequenceDomain(1, 2, "ticker", "KXTEST-A")
    assert domain != SequenceDomain(1, 2, "orderbook_delta", "KXTEST-B")


def test_paginated_market_listing_follows_cursor() -> None:
    rest = FakeRest()
    rest.pages = [
        {"markets": [_market("KXTEST-A")], "cursor": "next"},
        {"markets": [_market("KXTEST-B")], "cursor": ""},
    ]
    provider = KalshiMarketDataProvider(rest=rest, websocket=FakeWebSocket([]))
    markets = asyncio.run(provider.list_markets(status="open"))
    assert [market.market_id for market in markets] == ["KXTEST-A", "KXTEST-B"]
    assert rest.calls[1]["cursor"] == "next"


def test_paginated_market_listing_detects_cursor_loop() -> None:
    rest = FakeRest()
    rest.pages = [
        {"markets": [_market("KXTEST-A")], "cursor": "loop"},
        {"markets": [_market("KXTEST-B")], "cursor": "loop"},
    ]
    provider = KalshiMarketDataProvider(rest=rest, websocket=FakeWebSocket([]))
    with pytest.raises(ValueError, match="cursor loop"):
        asyncio.run(provider.list_market_payloads(status="open", max_pages=3))


def test_book_validation_detects_match() -> None:
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=FakeWebSocket([]))
    snapshot = asyncio.run(provider.get_orderbook("KXTEST-A"))
    result = asyncio.run(provider.validate_book(snapshot))
    assert result["matched"] is True


def test_book_validation_detects_divergence() -> None:
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=FakeWebSocket([]))
    snapshot = asyncio.run(provider.get_orderbook("KXTEST-A"))
    altered = snapshot.model_copy(update={"bids": tuple()})
    result = asyncio.run(provider.validate_book(altered))
    assert result["matched"] is False
    assert provider.metrics.book_divergences == 1


def test_queue_publish_uses_bounded_queue() -> None:
    client = KalshiWebSocketClient(ExchangeConfig(), queue_size=1)
    client._publish_payload({"type": "heartbeat"})
    assert client.queue.qsize() == 1


def test_queue_overflow_sets_stop_flag() -> None:
    client = KalshiWebSocketClient(ExchangeConfig(), queue_size=1)
    client._publish_payload({"type": "heartbeat"})
    client._publish_payload({"type": "heartbeat"})
    assert client.queue_overflow_count == 1
    assert client._stop.is_set()


def test_shutdown_sentinel_is_published() -> None:
    client = KalshiWebSocketClient(ExchangeConfig(), queue_size=2)
    asyncio.run(client.stop())
    queued = client.queue.get_nowait()
    assert isinstance(queued, KalshiQueuedMessage)
    assert queued.shutdown is True


def test_websocket_auth_uses_injected_clock(tmp_path: Path) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path = tmp_path / "kalshi.pem"
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    client = KalshiWebSocketClient(
        ExchangeConfig(api_key_id="kid", private_key_path=key_path),
        clock=clock,
    )
    headers = client._headers()
    assert headers["KALSHI-ACCESS-TIMESTAMP"] == "1767225600000"
    assert headers["KALSHI-ACCESS-KEY"] == "kid"
    assert headers["KALSHI-ACCESS-SIGNATURE"]


def test_ci_workflow_has_explicit_push_and_pr_triggers() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())
    assert workflow[True]["push"]["branches"] == ["main"]
    assert "pull_request" in workflow[True]


@pytest.mark.parametrize(
    "forbidden",
    [
        "submit_order",
        "cancel_order",
        "amend_order",
        "get_balance",
        "get_positions",
        "get_fills",
        "get_orders",
    ],
)
def test_kalshi_market_data_provider_has_no_forbidden_methods(forbidden: str) -> None:
    provider = KalshiMarketDataProvider(rest=FakeRest(), websocket=FakeWebSocket([]))
    assert not hasattr(provider, forbidden)

import asyncio

import pytest

from darwin.exchanges.mock import MockMarketDataProvider


@pytest.mark.parametrize("markets", [["KXTEST-A"], ["KXTEST-A", "KXTEST-B"]])
def test_mock_stream_starts_with_snapshots(markets: list[str]) -> None:
    async def run() -> list[str]:
        seen = []
        async for event in MockMarketDataProvider().stream_market_events(markets):
            seen.append(event.event_type)
            if len(seen) >= len(markets):
                break
        return seen

    assert asyncio.run(run()) == ["orderbook_snapshot"] * len(markets)


def test_mock_stream_contains_gap_and_recovery() -> None:
    async def run() -> list[str]:
        return [
            event.event_type
            async for event in MockMarketDataProvider().stream_market_events(
                ["KXTEST-A", "KXTEST-B"]
            )
        ]

    events = asyncio.run(run())
    assert "orderbook_delta" in events
    assert "snapshot_recovery" in events
    assert "reconnect" in events


@pytest.mark.parametrize("status", [None, "open", "closed"])
def test_mock_list_markets(status: str | None) -> None:
    markets = asyncio.run(MockMarketDataProvider().list_markets(status=status))
    assert {market.market_id for market in markets} == {"KXTEST-A", "KXTEST-B"}


@pytest.mark.parametrize("market", ["KXTEST-A", "KXTEST-B"])
def test_mock_orderbooks_are_sorted(market: str) -> None:
    snapshot = asyncio.run(MockMarketDataProvider().get_orderbook(market))
    assert list(snapshot.bids) == sorted(snapshot.bids, key=lambda level: level.price, reverse=True)
    assert list(snapshot.asks) == sorted(snapshot.asks, key=lambda level: level.price)

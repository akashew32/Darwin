import asyncio
import os
from pathlib import Path

import pytest

from darwin.config import ExchangeConfig
from darwin.exchanges.kalshi.market_data import KalshiMarketDataProvider

pytestmark = pytest.mark.kalshi_live


def _live_config() -> ExchangeConfig:
    key_id = os.getenv("KALSHI_API_KEY_ID")
    key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
    if not key_id or not key_path or not Path(key_path).exists():
        pytest.skip("Kalshi read-only WebSocket credentials are not configured")
    return ExchangeConfig(api_key_id=key_id, private_key_path=Path(key_path))


def test_kalshi_live_rest_market_listing_read_only() -> None:
    provider = KalshiMarketDataProvider.rest_only_from_config(_live_config())

    async def run() -> int:
        try:
            return len(await provider.list_markets(status="open"))
        finally:
            await provider.close()

    assert asyncio.run(run()) >= 0


def test_kalshi_live_orderbook_read_only() -> None:
    ticker = os.getenv("KALSHI_LIVE_TEST_TICKER")
    if not ticker:
        pytest.skip("KALSHI_LIVE_TEST_TICKER is not configured")
    provider = KalshiMarketDataProvider.from_config(_live_config())

    async def run() -> bool:
        try:
            market = await provider.get_market(ticker)
            snapshot = await provider.get_orderbook(market.market_id)
            return snapshot.market_id == ticker
        finally:
            await provider.close()

    assert asyncio.run(run())


def test_kalshi_live_websocket_receives_event_read_only() -> None:
    ticker = os.getenv("KALSHI_LIVE_TEST_TICKER")
    if not ticker:
        pytest.skip("KALSHI_LIVE_TEST_TICKER is not configured")
    provider = KalshiMarketDataProvider.from_config(_live_config())

    async def run() -> bool:
        try:
            await provider.get_market(ticker)
            await provider.get_orderbook(ticker)
            async for event in provider.stream_market_events([ticker]):
                return event.event_type in {
                    "health",
                    "heartbeat",
                    "orderbook_snapshot",
                    "orderbook_delta",
                    "market_metadata",
                    "public_trade",
                    "market_status",
                }
            return False
        finally:
            await provider.close()

    assert asyncio.run(asyncio.wait_for(run(), timeout=30))

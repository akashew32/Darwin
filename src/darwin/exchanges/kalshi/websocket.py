import asyncio
import json
import random
import time
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit

import websockets

from darwin.clock import Clock, SystemClock
from darwin.config import ExchangeConfig
from darwin.exchanges.kalshi.auth import KalshiAuth
from darwin.exchanges.kalshi.exceptions import KalshiAuthenticationError
from darwin.logging import get_logger


class KalshiWebSocketClient:
    def __init__(
        self,
        config: ExchangeConfig,
        *,
        clock: Clock | None = None,
        queue_size: int = 10_000,
    ) -> None:
        self.config = config
        self.clock = clock or SystemClock()
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_size)
        self.auth = KalshiAuth.from_config(config) if config.has_credentials else None
        self.logger = get_logger("darwin.kalshi.websocket")
        self._stop = asyncio.Event()
        self.reconnect_count = 0
        self.last_message_monotonic: float | None = None

    def _headers(self) -> dict[str, str]:
        if self.auth is None:
            raise KalshiAuthenticationError("authenticated WebSocket requires Kalshi credentials")
        timestamp = str(int(time.time() * 1000))
        path = urlsplit(self.config.websocket_url).path
        return self.auth.headers(timestamp, "GET", path)

    async def stop(self) -> None:
        self._stop.set()

    async def connect_and_subscribe(
        self,
        channels: list[str],
        market_tickers: list[str],
    ) -> AsyncIterator[dict[str, Any]]:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    self.config.websocket_url,
                    additional_headers=self._headers(),
                    ping_interval=20,
                    ping_timeout=20,
                    max_queue=1024,
                ) as ws:
                    await ws.send(
                        json.dumps(
                            {
                                "id": 1,
                                "cmd": "subscribe",
                                "params": {"channels": channels, "market_tickers": market_tickers},
                            }
                        )
                    )
                    backoff = 1.0
                    async for raw in ws:
                        self.last_message_monotonic = time.monotonic()
                        payload = json.loads(raw)
                        if not isinstance(payload, dict):
                            continue
                        yield payload
            except (OSError, websockets.WebSocketException, json.JSONDecodeError) as exc:
                self.reconnect_count += 1
                self.logger.warning(
                    "kalshi_ws_reconnect", error=str(exc), count=self.reconnect_count
                )
                await asyncio.sleep(backoff + random.uniform(0, 0.25))
                backoff = min(backoff * 2, 30)

    def stale_seconds(self) -> float | None:
        if self.last_message_monotonic is None:
            return None
        return time.monotonic() - self.last_message_monotonic

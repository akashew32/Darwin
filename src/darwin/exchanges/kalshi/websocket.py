import asyncio
import json
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

import websockets
from websockets.asyncio.client import ClientConnection

from darwin.clock import Clock, SystemClock
from darwin.config import ExchangeConfig
from darwin.exchanges.kalshi.auth import KalshiAuth
from darwin.exchanges.kalshi.exceptions import KalshiAuthenticationError
from darwin.logging import get_logger


@dataclass(frozen=True)
class KalshiSubscriptionSpec:
    request_id: int
    channels: tuple[str, ...]
    market_tickers: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        params: dict[str, Any] = {"channels": list(self.channels)}
        if self.market_tickers:
            params["market_tickers"] = list(self.market_tickers)
        return {"id": self.request_id, "cmd": "subscribe", "params": params}


@dataclass
class KalshiSubscriptionState:
    request_id: int
    subscription_id: int | None
    channels: tuple[str, ...]
    market_tickers: tuple[str, ...]
    acknowledged: bool
    created_ts: datetime
    last_message_ts: datetime | None = None
    reconnect_generation: int = 0


@dataclass
class KalshiQueuedMessage:
    payload: dict[str, Any] | None
    shutdown: bool = False


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
        self.queue: asyncio.Queue[KalshiQueuedMessage] = asyncio.Queue(maxsize=queue_size)
        self.auth = KalshiAuth.from_config(config) if config.has_credentials else None
        self.logger = get_logger("darwin.kalshi.websocket")
        self._stop = asyncio.Event()
        self._active_ws: ClientConnection | None = None
        self.reconnect_count = 0
        self.messages_received = 0
        self.malformed_messages = 0
        self.queue_overflow_count = 0
        self.connection_generation = 0
        self.last_message_ts: datetime | None = None
        self.subscriptions: dict[int, KalshiSubscriptionState] = {}

    def _headers(self) -> dict[str, str]:
        if self.auth is None:
            raise KalshiAuthenticationError("authenticated WebSocket requires Kalshi credentials")
        timestamp = str(int(self.clock.now().timestamp() * 1000))
        path = urlsplit(self.config.websocket_url).path
        return self.auth.headers(timestamp, "GET", path)

    async def stop(self) -> None:
        self._stop.set()
        if self._active_ws is not None:
            await self._active_ws.close()
        await self._publish_sentinel()

    async def _publish_sentinel(self) -> None:
        try:
            self.queue.put_nowait(KalshiQueuedMessage(payload=None, shutdown=True))
        except asyncio.QueueFull:
            _ = self.queue.get_nowait()
            self.queue.put_nowait(KalshiQueuedMessage(payload=None, shutdown=True))

    async def connect_and_subscribe(
        self,
        channels: list[str],
        market_tickers: list[str],
    ) -> AsyncIterator[dict[str, Any]]:
        specs = build_subscription_specs(market_tickers, start_request_id=1)
        async for payload in self.connect_with_specs(specs):
            yield payload

    async def connect_with_specs(
        self,
        specs: list[KalshiSubscriptionSpec],
    ) -> AsyncIterator[dict[str, Any]]:
        reader = asyncio.create_task(self._reader_loop(specs))
        try:
            while True:
                queued = await self.queue.get()
                if queued.shutdown:
                    break
                if queued.payload is not None:
                    yield queued.payload
        finally:
            await self.stop()
            reader.cancel()
            try:
                await reader
            except asyncio.CancelledError:
                pass

    async def _reader_loop(self, specs: list[KalshiSubscriptionSpec]) -> None:
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
                    self._active_ws = ws
                    self.connection_generation += 1
                    self.subscriptions.clear()
                    self.logger.info("kalshi_ws_connected", url=self.config.websocket_url)
                    for spec in specs:
                        self.subscriptions[spec.request_id] = KalshiSubscriptionState(
                            request_id=spec.request_id,
                            subscription_id=None,
                            channels=spec.channels,
                            market_tickers=spec.market_tickers,
                            acknowledged=False,
                            created_ts=self.clock.now(),
                            reconnect_generation=self.connection_generation,
                        )
                        await ws.send(json.dumps(spec.payload()))
                        self.logger.info(
                            "kalshi_ws_subscription_sent",
                            request_id=spec.request_id,
                            channels=spec.channels,
                            market_count=len(spec.market_tickers),
                            generation=self.connection_generation,
                        )
                    backoff = 1.0
                    async for raw in ws:
                        self.last_message_ts = self.clock.now()
                        self.messages_received += 1
                        try:
                            payload = json.loads(raw)
                        except json.JSONDecodeError:
                            self.malformed_messages += 1
                            self.logger.warning("kalshi_ws_malformed_json")
                            continue
                        if not isinstance(payload, dict):
                            self.malformed_messages += 1
                            continue
                        self._record_ack(payload)
                        self._publish_payload(payload)
            except (OSError, websockets.WebSocketException, json.JSONDecodeError) as exc:
                self._active_ws = None
                if self._stop.is_set():
                    break
                self.reconnect_count += 1
                self.logger.warning(
                    "kalshi_ws_reconnect", error=str(exc), count=self.reconnect_count
                )
                try:
                    await asyncio.wait_for(
                        self._stop.wait(),
                        timeout=backoff + random.uniform(0, 0.25),
                    )
                except TimeoutError:
                    pass
                backoff = min(backoff * 2, 30)
            finally:
                self._active_ws = None
        await self._publish_sentinel()

    def _publish_payload(self, payload: dict[str, Any]) -> None:
        try:
            self.queue.put_nowait(KalshiQueuedMessage(payload=payload))
        except asyncio.QueueFull:
            self.queue_overflow_count += 1
            self.logger.error("kalshi_ws_queue_overflow", maxsize=self.queue.maxsize)
            self._stop.set()

    def _record_ack(self, payload: dict[str, Any]) -> None:
        if payload.get("type") != "subscribed":
            return
        request_id = payload.get("id")
        msg = payload.get("msg")
        if not isinstance(request_id, int) or not isinstance(msg, dict):
            return
        state = self.subscriptions.get(request_id)
        if state is None:
            return
        state.subscription_id = int(msg["sid"]) if "sid" in msg else None
        state.acknowledged = True
        state.last_message_ts = self.clock.now()
        self.logger.info(
            "kalshi_ws_subscription_ack",
            request_id=request_id,
            subscription_id=state.subscription_id,
            channel=msg.get("channel"),
            generation=self.connection_generation,
        )

    def stale_seconds(self) -> float | None:
        if self.last_message_ts is None:
            return None
        return (self.clock.now() - self.last_message_ts).total_seconds()


def build_subscription_specs(
    market_tickers: list[str],
    *,
    start_request_id: int = 1,
) -> list[KalshiSubscriptionSpec]:
    return [
        KalshiSubscriptionSpec(
            request_id=start_request_id,
            channels=("orderbook_delta", "ticker", "trade"),
            market_tickers=tuple(market_tickers),
        ),
        KalshiSubscriptionSpec(
            request_id=start_request_id + 1,
            channels=("market_lifecycle_v2",),
            market_tickers=(),
        ),
    ]

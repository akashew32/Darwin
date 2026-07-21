import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx

from darwin.config import ExchangeConfig
from darwin.exchanges.kalshi.auth import KalshiAuth
from darwin.exchanges.kalshi.exceptions import KalshiAuthenticationError, KalshiRateLimitError
from darwin.logging import get_logger


class AsyncTokenBucket:
    """Small async token bucket for read-only REST pacing."""

    def __init__(self, rate_per_second: float, capacity: float) -> None:
        self.rate_per_second = rate_per_second
        self.capacity = capacity
        self.tokens = capacity
        self.updated_at = time.monotonic()

    async def acquire(self, cost: float = 1.0) -> None:
        import asyncio

        while True:
            now = time.monotonic()
            elapsed = now - self.updated_at
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_second)
            self.updated_at = now
            if self.tokens >= cost:
                self.tokens -= cost
                return
            await asyncio.sleep((cost - self.tokens) / self.rate_per_second)


class KalshiRestClient:
    def __init__(self, config: ExchangeConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self.auth = KalshiAuth.from_config(config) if config.has_credentials else None
        self.client = client or httpx.AsyncClient(
            base_url=config.rest_base_url,
            timeout=config.request_timeout_seconds,
        )
        self.logger = get_logger("darwin.kalshi.rest")
        self.rate_limiter = AsyncTokenBucket(rate_per_second=10, capacity=20)

    async def close(self) -> None:
        await self.client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        authenticated: bool = False,
    ) -> dict[str, Any]:
        return await self._request_with_validation(
            method,
            path,
            params=params,
            json=json,
            authenticated=authenticated,
            validator=lambda payload: payload,
        )

    async def _request_with_validation(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        authenticated: bool = False,
        validator: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        import asyncio

        retries = 3
        backoff = 0.25
        for attempt in range(retries + 1):
            await self.rate_limiter.acquire()
            headers: dict[str, str] = {}
            if authenticated:
                if self.auth is None:
                    raise KalshiAuthenticationError("Kalshi credentials are required")
                timestamp = str(int(time.time() * 1000))
                path_without_query = urlsplit(path).path
                headers.update(self.auth.headers(timestamp, method, path_without_query))
            started = time.monotonic()
            try:
                response = await self.client.request(
                    method,
                    path,
                    params=params,
                    json=json,
                    headers=headers,
                )
                latency_ms = (time.monotonic() - started) * 1000
                self.logger.info(
                    "kalshi_rest_request",
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    latency_ms=round(latency_ms, 2),
                )
                if response.status_code == 429:
                    if attempt == retries:
                        raise KalshiRateLimitError("Kalshi rate limit exceeded")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 4)
                    continue
                if response.status_code >= 500 and attempt < retries:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 4)
                    continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Kalshi response must be a JSON object")
                return validator(payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                self.logger.warning(
                    "kalshi_rest_retry",
                    method=method,
                    path=path,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt == retries:
                    raise
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 4)
        raise RuntimeError("unreachable Kalshi REST retry state")

    async def get_events(self, limit: int = 100) -> dict[str, Any]:
        return await self.request("GET", "/trade-api/v2/events", params={"limit": limit})

    async def get_markets(
        self,
        status: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
        event_ticker: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        if event_ticker:
            params["event_ticker"] = event_ticker
        if category:
            params["category"] = category
        return await self._request_with_validation(
            "GET",
            "/trade-api/v2/markets",
            params=params,
            validator=_require_markets,
        )

    async def get_market(self, market_ticker: str) -> dict[str, Any]:
        return await self._request_with_validation(
            "GET",
            f"/trade-api/v2/markets/{market_ticker}",
            validator=_require_market,
        )

    async def get_orderbook(self, market_ticker: str) -> dict[str, Any]:
        return await self._request_with_validation(
            "GET",
            f"/trade-api/v2/markets/{market_ticker}/orderbook",
            validator=_require_orderbook,
        )

    async def get_balance(self) -> dict[str, Any]:
        return await self.request("GET", "/trade-api/v2/portfolio/balance", authenticated=True)

    async def submit_order(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/trade-api/v2/portfolio/orders",
            json=payload,
            authenticated=True,
        )

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        return await self.request(
            "DELETE",
            f"/trade-api/v2/portfolio/orders/{order_id}",
            authenticated=True,
        )

    async def get_fills(self) -> dict[str, Any]:
        return await self.request("GET", "/trade-api/v2/portfolio/fills", authenticated=True)

    async def get_orders(self, status: str | None = None) -> dict[str, Any]:
        params = {"status": status} if status else None
        return await self.request(
            "GET",
            "/trade-api/v2/portfolio/orders",
            params=params,
            authenticated=True,
        )

    async def get_positions(self) -> dict[str, Any]:
        return await self.request("GET", "/trade-api/v2/portfolio/positions", authenticated=True)


def _require_markets(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("markets"), list):
        raise ValueError("Kalshi markets response missing markets list")
    return payload


def _require_market(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("market"), dict):
        raise ValueError("Kalshi market response missing market object")
    return payload


def _require_orderbook(payload: dict[str, Any]) -> dict[str, Any]:
    book = payload.get("orderbook_fp") or payload.get("orderbook")
    if not isinstance(book, dict):
        raise ValueError("Kalshi orderbook response missing orderbook object")
    if not isinstance(book.get("yes_dollars") or book.get("yes"), list):
        raise ValueError("Kalshi orderbook response missing YES levels")
    if not isinstance(book.get("no_dollars") or book.get("no"), list):
        raise ValueError("Kalshi orderbook response missing NO levels")
    return payload

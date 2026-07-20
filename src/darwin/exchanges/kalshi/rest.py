import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx

from darwin.config import ExchangeConfig
from darwin.exchanges.kalshi.auth import KalshiAuth
from darwin.exchanges.kalshi.exceptions import KalshiAuthenticationError, KalshiRateLimitError


class KalshiRestClient:
    def __init__(self, config: ExchangeConfig, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self.auth = KalshiAuth.from_config(config) if config.has_credentials else None
        self.client = client or httpx.AsyncClient(
            base_url=config.rest_base_url,
            timeout=config.request_timeout_seconds,
        )

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
        headers: dict[str, str] = {}
        if authenticated:
            if self.auth is None:
                raise KalshiAuthenticationError("Kalshi credentials are required for this request")
            timestamp = str(int(time.time() * 1000))
            path_without_query = urlsplit(path).path
            headers.update(self.auth.headers(timestamp, method, path_without_query))
        response = await self.client.request(
            method, path, params=params, json=json, headers=headers
        )
        if response.status_code == 429:
            raise KalshiRateLimitError("Kalshi rate limit exceeded")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Kalshi response must be a JSON object")
        return payload

    async def get_events(self, limit: int = 100) -> dict[str, Any]:
        return await self.request("GET", "/trade-api/v2/events", params={"limit": limit})

    async def get_markets(self, status: str | None = None, limit: int = 100) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        return await self.request("GET", "/trade-api/v2/markets", params=params)

    async def get_orderbook(self, market_ticker: str) -> dict[str, Any]:
        return await self.request("GET", f"/trade-api/v2/markets/{market_ticker}/orderbook")

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

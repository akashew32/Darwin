# Exchange Integration

Kalshi is the first exchange. Exchange details are isolated under
`src/darwin/exchanges/kalshi`.

Verified choices, rechecked on 2026-07-20 against official Kalshi
documentation:

- Production REST base URL: `https://external-api.kalshi.com/trade-api/v2`.
- Demo REST base URL: `https://external-api.demo.kalshi.co/trade-api/v2`.
- Production WebSocket URL:
  `wss://external-api-ws.kalshi.com/trade-api/ws/v2`.
- Demo WebSocket URL:
  `wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2`.
- Auth headers: `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-SIGNATURE`, `KALSHI-ACCESS-TIMESTAMP`.
- WebSocket signature payload: `timestamp + "GET" + "/trade-api/ws/v2"`.
- REST signature payload: `timestamp + method + path_without_query`, excluding
  host and query string.
- Binary book normalization converts YES bids and NO bids into Darwin YES bid/ask prices.
- Public REST market-data endpoints can list markets, retrieve a single market,
  retrieve order books, and retrieve trades without authentication.
- WebSocket market data requires an authenticated WebSocket handshake. Public
  channels do not add channel-level authorization beyond that session.
- Authenticated account endpoints remain outside the live-paper execution path.
- Current V2 create-order endpoint is
  `POST /trade-api/v2/portfolio/events/orders`; Darwin does not call it from
  paper-live.
- Current V2 cancel endpoint is `DELETE /trade-api/v2/portfolio/events/orders/{order_id}`;
  Darwin does not call it from paper-live.
- Current V2 order payload uses `ticker`, `client_order_id`, book `side`
  (`bid`/`ask`), fixed-point `count`, fixed-point dollar `price`,
  `time_in_force`, and self-trade-prevention fields.
- WebSocket orderbook updates use channel `orderbook_delta`, send `orderbook_snapshot` first, then deltas with `seq`; subscriptions use `market_ticker` or `market_tickers`.
- REST orderbook may provide fixed-point dollar fields in `orderbook_fp.yes_dollars` and `orderbook_fp.no_dollars`; WebSocket snapshots may use `yes_dollars_fp` and `no_dollars_fp`.
- WebSocket public trades use channel `trade` with `trade_id`,
  `market_ticker`, YES/NO fixed-point prices, `count_fp`, `taker_side`, and
  `ts_ms`.
- WebSocket market lifecycle uses channel `market_lifecycle_v2`; filters by
  market ticker are not supported for lifecycle messages.
- WebSocket keepalive can rely on the Python `websockets` ping/pong handling.
- WebSocket errors include numeric codes; code `9` means authentication required.
- Rate limits are token-based for authenticated requests. Public market-data REST
  should still apply backoff; authenticated 429 payloads may be
  `{"error": "too many requests"}` without retry headers.
- Reconnect expectations: reconnect with exponential backoff, resubscribe, and
  rebuild local order books from fresh snapshots before resuming decisions after
  sequence gaps.
- Live paper trading uses only read-only market-data methods. It must not call
  create, amend, or cancel order endpoints.

Credentialed verification still required:

- Real public WebSocket connectivity from the deployed environment when network
  access is available.
- Account-specific authenticated read-only market-data behavior and tier limits.
- Real order creation/cancellation remains intentionally out of scope for this
  phase.

`KalshiMarketDataProvider` is the paper-live integration point. It satisfies
`MarketDataProvider` with only `list_markets`, `get_market`, `get_orderbook`,
`stream_market_events`, and `close`.

Future exchanges should implement the same read-only market-data interface for
paper trading and keep execution adapters separate.

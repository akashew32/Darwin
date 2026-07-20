# Exchange Integration

Kalshi is the first exchange. All exchange details are isolated under `src/darwin/exchanges/kalshi`.

Verified choices, rechecked on 2026-07-20 against official Kalshi
documentation:

- REST: `/trade-api/v2`.
- WebSocket: `/trade-api/ws/v2`.
- Auth headers: `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-SIGNATURE`, `KALSHI-ACCESS-TIMESTAMP`.
- Signature payload: `timestamp + method + path_without_query`.
- Binary book normalization converts YES bids and NO bids into Darwin YES bid/ask prices.
- Public market-data endpoints can list markets and retrieve order books.
- Authenticated account endpoints remain outside the live-paper execution path.
- Current create-order endpoint: `POST /trade-api/v2/portfolio/orders`.
- Current cancel endpoint: `DELETE /trade-api/v2/portfolio/orders/{order_id}`.
- Current order create payload uses `ticker`, `side` (`yes`/`no`), `action` (`buy`/`sell`), `count` or `count_fp`, and `yes_price`/`no_price` or `yes_price_dollars`/`no_price_dollars`.
- WebSocket orderbook updates use channel `orderbook_delta`, send `orderbook_snapshot` first, then deltas with `seq`; subscriptions use `market_ticker` or `market_tickers`.
- REST orderbook may provide fixed-point dollar fields in `orderbook_fp.yes_dollars` and `orderbook_fp.no_dollars`; WebSocket snapshots may use `yes_dollars_fp` and `no_dollars_fp`.
- Live paper trading uses only read-only market-data methods. It must not call
  create, amend, or cancel order endpoints.

Credentialed verification still required:

- Real public WebSocket connectivity from the deployed environment when network
  access is available.
- Actual create/cancel order behavior in a funded or demo account.
- Account-specific pagination and rate-limit behavior for orders, fills, positions, and balance.
- Ambiguous timeout reconciliation using live order history.

Future exchanges should implement `ExchangeClient` and map raw payloads into immutable Darwin domain models.

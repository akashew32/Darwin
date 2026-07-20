# Exchange Integration

Kalshi is the first exchange. All exchange details are isolated under `src/darwin/exchanges/kalshi`.

Verified choices:

- REST: `/trade-api/v2`.
- WebSocket: `/trade-api/ws/v2`.
- Auth headers: `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-SIGNATURE`, `KALSHI-ACCESS-TIMESTAMP`.
- Signature payload: `timestamp + method + path_without_query`.
- Binary book normalization converts YES bids and NO bids into Darwin YES bid/ask prices.

Future exchanges should implement `ExchangeClient` and map raw payloads into immutable Darwin domain models.

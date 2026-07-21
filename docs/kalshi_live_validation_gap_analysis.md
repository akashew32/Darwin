# Kalshi Live Validation Gap Analysis

Updated: 2026-07-21.

## Existing Working Components

- `KalshiMarketDataProvider` is read-only and exposes no order, portfolio,
  balance, position, or fill methods.
- REST market, market-listing, and order-book reads are implemented with retries,
  validation, and structured logging.
- WebSocket authentication exists and signs the documented `/trade-api/ws/v2`
  path.
- `LivePaperTrader` accepts a `MarketDataProvider` plus local `PaperBroker`, so
  paper execution remains simulated.
- Mock paper-live and recorded Kalshi fixture tests pass offline.

## Gaps Found

- WebSocket subscriptions bundled `market_lifecycle_v2` with market-filtered
  channels, but the documented lifecycle feed is global.
- Subscription acknowledgement state was not modeled strongly enough to gate feed
  health.
- Sequence handling treated duplicates as recoverable gaps.
- Sequence domains were represented as an ad hoc `(sid, market)` tuple instead of
  an explicit key. Current docs show WebSocket messages carry `sid` and `seq`;
  Darwin now scopes orderbook sequences by connection generation, subscription
  id, channel, and market ticker.
- Reconnect handling did not explicitly clear old sequence baselines.
- WebSocket declared a queue but yielded directly from the socket iterator.
- `stop()` set a flag but did not close an active socket or interrupt reconnect
  sleep.
- Authentication timestamps used system time instead of the injected clock.
- Market listing did not follow pagination.
- `markets sync --environment kalshi`, `markets list-live`, and
  `validate-kalshi-feed` were missing.
- Dry-run reports lacked dedicated connection/subscription/sequence/book
  validation artifacts.
- `execution_endpoint_calls` was self-reported rather than instrumented from a
  boundary object.
- GitHub Actions used shorthand triggers and did not run explicit smoke/fixture
  tests.

## Verified Kalshi Behaviors

- REST base URLs are `https://external-api.kalshi.com/trade-api/v2` and
  `https://external-api.demo.kalshi.co/trade-api/v2`.
- WebSocket URLs are
  `wss://external-api-ws.kalshi.com/trade-api/ws/v2` and
  `wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2`.
- WebSocket handshakes require Kalshi auth headers.
- Market-filtered channels include `orderbook_delta`, `ticker`, and `trade`.
- `market_lifecycle_v2` is a global lifecycle channel and should not include
  market ticker filters.
- Subscribe acknowledgements include request `id`, message `channel`, and
  subscription id `sid`.
- Orderbook snapshots precede deltas and include `sid` and `seq`.
- Rate limiting is token based; `429` payloads may only contain
  `{"error": "too many requests"}`.

## Implementation Sequence

1. Split subscriptions and track acknowledgements.
2. Add explicit sequence domains with duplicate/backward/gap behavior.
3. Reset connection-generation state on reconnect.
4. Use a real bounded raw-message queue and interruptible shutdown.
5. Add paginated market discovery and pre-stream market validation.
6. Expand dry-run validation reports and REST/local book checks.
7. Harden credentials and safety-boundary instrumentation.
8. Add CI visibility and opt-in credentialed tests.

## Acceptance Criteria

- Mock paper-live still passes.
- Kalshi dry-run fails closed without credentials and can validate connectivity
  when credentials are present.
- Offline tests exceed 190 and include fixtures for subscriptions, sequences,
  shutdown, queue behavior, market discovery, book validation, credentials,
  safety boundaries, and CI workflow parsing.

# Live Paper Trading Gap Analysis

Updated: 2026-07-20.

## Existing Functionality

- Replay-based paper simulation exists through `darwin paper`.
- Event-driven backtesting uses normalized snapshots/deltas, stateful features, strategy decisions, risk checks, simulated fills, accounting, and report outputs.
- Kalshi REST client can list events/markets and fetch orderbooks.
- Kalshi WebSocket client connects, signs the handshake when credentials exist, subscribes, and reconnects with exponential backoff.
- Local order books apply snapshots and sequence-checked deltas.
- Simulated broker supports multi-level marketable partial fills.

## Current Gaps

- There is no dedicated `paper-live` service boundary.
- Replay paper is named separately but live data paper trading does not exist yet.
- WebSocket queue fields exist but are not used as a normalized event pipeline.
- Sequence gaps are detected in local books but not surfaced into session health or recovery events.
- Paper orders fill immediately in backtests; live paper needs latency-aware outstanding orders across events.
- Equity currently needs an explicit documented function rather than ad hoc report formulas.
- Trade-level P&L needs closed-lot records instead of cumulative snapshots.
- Persistence is report-oriented, not a durable normalized event store.
- Dashboard reads report files but not active session database state.
- `markets sync` and `collect` need mock/live read-only behavior instead of empty-file output.

## Safety Audit

- `PaperBroker` inherits from `SimulatedBroker` and has no exchange-order submission methods.
- `LiveBroker` is separate and guarded.
- The new live-paper service must depend on a read-only `MarketDataProvider` protocol and a paper broker only.
- Paper-live must never receive or instantiate `LiveBroker` or call Kalshi order create/amend/cancel endpoints.

## Hardcoded Or Incomplete Settings

- Backtest currently uses fixed 5 bps slippage.
- Strategy stop-loss/take-profit thresholds are hardcoded.
- Risk uses some fixed circuit-breaker thresholds.
- Seed is accepted but not yet used by deterministic/probabilistic execution.
- Paper execution latency is not yet modeled.

## Kalshi Behavior Verified

Verified against official Kalshi docs on 2026-07-20:

- Production REST base: `https://external-api.kalshi.com/trade-api/v2`.
- Demo REST base: `https://external-api.demo.kalshi.co/trade-api/v2`.
- Production WebSocket: `wss://external-api-ws.kalshi.com/trade-api/ws/v2`.
- Demo WebSocket: `wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2`.
- Single market orderbook endpoint `GET /markets/{ticker}/orderbook` is public and returns `orderbook_fp`.
- WebSocket handshake requires API-key headers even for public market-data channels.
- Public channels include `ticker`, `trade`, `market_lifecycle_v2`, and related market-data channels.
- `orderbook_delta` sends an initial `orderbook_snapshot` and then `orderbook_delta` messages.
- Orderbook fixed-point arrays are bid-only: `yes_dollars` and `no_dollars`; YES asks are implied by complementary NO bids.
- Lifecycle statuses include `initialized`, `active`, `inactive`, `closed`, `determined`, `disputed`, `amended`, and `finalized`.

Credentialed verification still required:

- Real WebSocket auth/connect/subscription behavior.
- Live reconnect and resubscription behavior.
- Live market lifecycle and public trade schemas over a real stream.

## Implementation Sequence

1. Add explicit equity and closed-trade accounting helpers.
2. Add read-only market-data provider protocol.
3. Add normalized async event types and bounded event bus.
4. Add deterministic mock exchange provider for tests and smoke runs.
5. Add live paper service using only read-only provider and `PaperBroker`.
6. Add latency-aware paper order processing and session reports.
7. Add CLI `paper-live`, mock `markets sync`, and mock `collect`.
8. Add API/dashboard session-state readers.
9. Expand tests to at least 120 behavior tests.

## Acceptance Criteria For This Pass

- `darwin paper-live --exchange-environment mock ...` runs end to end.
- The paper-live code path has no dependency on exchange execution adapters.
- Initial snapshots precede deltas.
- Sequence gaps pause decisions and trigger snapshot recovery.
- Queue overflow halts trading safely.
- Paper session state is persisted to SQLite/report artifacts.
- At least 120 tests pass without credentials.

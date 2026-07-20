# Darwin Implementation Gap Analysis

Updated: 2026-07-20.

## Existing Working Components

- Project packaging, Ruff, mypy, pytest, Docker, GitHub Actions, and basic CLI wiring exist.
- Immutable domain models exist for markets, order books, orders, fills, positions, portfolio state, feature vectors, signals, and risk decisions.
- Kalshi REST/WebSocket/auth modules exist and RSA-PSS signing follows the documented header model.
- Local order book reconstruction from snapshot plus deltas exists.
- Basic replay JSONL reader/writer exists.
- Basic microstructure feature extraction exists.
- A momentum signal scaffold exists.
- A persistent kill switch exists.
- Basic portfolio accounting handles buy fills and duplicate fill idempotency.
- A read-only Streamlit dashboard shell exists.

## Placeholder Or Incomplete Components

- `darwin backtest`, `darwin walk-forward`, `darwin paper`, `darwin collect`, `darwin report`, `darwin features build`, `darwin model train`, `darwin markets sync`, `darwin markets rank`, `darwin reconcile`, and `darwin cancel-all` mostly printed placeholder text.
- Backtester generated orders but did not pass them through risk, did not update order manager state, did not apply fills to portfolio, and did not persist outputs.
- Paper trading was not a functional loop.
- Dashboard did not read persisted results.
- Storage schema only held raw messages.
- Tests covered only a small subset of core behavior.

## Incorrect Implementations

- Risk open-order limit incorrectly used `len(portfolio.positions)`.
- Strategy client order IDs used integer seconds and could collide.
- Strategy was not position-aware and had no exit lifecycle.
- Simulated broker assumed a top-of-book touch fully filled the whole order.
- Sell accounting reduced quantities but did not calculate realized P&L correctly.
- Kalshi order submission used `/trade-api/v2/portfolio/events/orders`; current docs use `/trade-api/v2/portfolio/orders`.
- Kalshi order payload used `side=bid/ask`; current docs use `side=yes/no` and `action=buy/sell`.

## Missing Tests

- End-to-end backtest.
- Backtest report output.
- Strategy exits, stop-loss, take-profit, cooldown, duplicate-open-order prevention.
- Multi-level fills and partial fills.
- Risk rule coverage.
- Order transition validation and duplicate-fill idempotency.
- Walk-forward running out-of-sample backtests.
- Paper-trading loop against mock live data.
- CLI command behavior.
- Kalshi request construction and documented fixture mapping.

## Exchange Behaviors Requiring Verification

Verified against official Kalshi docs during this pass:

- `POST /trade-api/v2/portfolio/orders` creates orders.
- `DELETE /trade-api/v2/portfolio/orders/{order_id}` cancels/reduces remaining contracts.
- `GET /trade-api/v2/markets/{ticker}/orderbook` returns `orderbook_fp` with `yes_dollars` and `no_dollars`, and WebSocket orderbook messages may use `yes_dollars_fp` / `no_dollars_fp`.
- WebSocket orderbook channel is `orderbook_delta`, sends `orderbook_snapshot` first, then `orderbook_delta`, and requires `market_ticker(s)`.
- Auth headers are `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-SIGNATURE`, `KALSHI-ACCESS-TIMESTAMP`; timestamp is milliseconds.

Still requiring credentialed verification:

- Authenticated order create/cancel responses on a real demo account.
- Account-specific rate-limit behavior.
- Position/balance/fill pagination with real account data.
- Ambiguous timeout reconciliation against live order history.

## Prioritized Implementation Sequence

1. Replace placeholder CLI with functional local/offline commands.
2. Implement deterministic replay events and sample multi-market fixture.
3. Strengthen portfolio accounting and settlement.
4. Implement order manager transitions and deterministic collision-resistant IDs.
5. Replace fill simulation with multi-level marketable and conservative passive fill behavior.
6. Expand risk context and fix open-order handling.
7. Make momentum strategy position-aware with exits.
8. Replace backtester with end-to-end risk-gated portfolio-updating reports.
9. Implement walk-forward using true out-of-sample backtest runs.
10. Implement mock/live-data paper trading loop that never submits exchange orders.
11. Expand storage, dashboard reads, docs, and tests.

## Acceptance Criteria For This Pass

- `darwin backtest --input tests/replay/multi_market_session.jsonl --output reports/backtests/sample` produces non-empty reports and changed portfolio state.
- Every proposed order in backtest/paper passes through the risk engine.
- Partial fills, duplicate fills, fees, slippage, exits, realized P&L, and settlement are tested.
- `darwin walk-forward` runs true backtests on test folds and writes aggregate reports.
- `darwin paper --input tests/replay/multi_market_session.jsonl --markets ...` runs an end-to-end mock session.
- CLI commands no longer emit placeholder “ready” text.
- At least 75 meaningful tests pass without credentials or external network access.
- Ruff and strict mypy pass.
- Live trading remains disabled by default.

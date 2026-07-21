# Darwin Progress

## 2026-07-20

- Audited Git history: one initial implementation commit (`1daf27a`).
- Audited source tree, tests, docs, CLI, strategy, risk, backtest, order manager, simulated broker, and portfolio accounting.
- Found placeholder CLI commands, incomplete backtest, incomplete paper trading, risk open-order bug, client-order-ID collision risk, shallow fill simulation, and incorrect Kalshi order endpoint/payload.
- Verified current Kalshi docs for orderbook WebSocket messages, REST orderbook, order create, cancel order, authentication headers, and timestamp units.
- Created `docs/implementation_gap_analysis.md`.

## Commands Run

```bash
git log --oneline --decorate --max-count=20
find src tests docs config scripts -type f | sort
rg -n "NotImplementedError|typer\\.echo\\(|pass|TODO|FIXME|ready|future release|placeholder" ...
git ls-files | head -200
```

## Remaining Work

- Implement the working end-to-end vertical path.
- Expand tests and run final verification.
- Commit in small groups and push to GitHub.

## Core Vertical Path Slice

- Strengthened portfolio accounting with realized P&L, duplicate fill idempotency, and settlement.
- Added deterministic client order IDs.
- Replaced the order manager with transition tracking and duplicate-fill handling.
- Replaced top-of-book full-fill assumption with visible multi-level partial fill simulation.
- Added risk context and fixed open-order counting.
- Made momentum strategy position-aware with exit, stop-loss/take-profit, and non-colliding order IDs.
- Replaced the backtest engine with an event loop that updates books, features, strategy, risk, fills, portfolio, metrics, and reports.
- Added `tests/replay/multi_market_session.jsonl`.
- Smoke ran:

```bash
.venv/bin/darwin backtest --input tests/replay/multi_market_session.jsonl --output reports/backtests/sample
```

Result: generated summary, CSVs, and HTML report with nonzero fees, spread cost, net P&L, partial entry fill, exit, settlement, and one risk rejection.

## Walk-Forward, Paper, Kalshi, Dashboard Slice

- Implemented `darwin walk-forward` using the event-driven backtester for frozen test windows.
- Implemented `darwin paper` against replay/mock live data, explicitly with no live order submission.
- Corrected Kalshi create-order endpoint and payload shape from current official docs.
- Extended Kalshi orderbook mapper to support fixed-point dollar orderbook schemas.
- Replaced the static dashboard with report-backed read-only tables.
- Added stateful incremental features and switched the backtester to use them.

Smoke commands:

```bash
.venv/bin/darwin walk-forward --input tests/replay/multi_market_session.jsonl --output reports/walk_forward/sample
.venv/bin/darwin paper --markets KXTEST-YES,KXTEST-REJECT --input tests/replay/multi_market_session.jsonl --output reports/paper/sample
```

## Final Verification

Passed:

```bash
PATH="$PWD/.venv/bin:$PATH" make lint
PATH="$PWD/.venv/bin:$PATH" make typecheck
PATH="$PWD/.venv/bin:$PATH" make test
PATH="$PWD/.venv/bin:$PATH" darwin doctor
PATH="$PWD/.venv/bin:$PATH" darwin db migrate
PATH="$PWD/.venv/bin:$PATH" darwin replay tests/replay/multi_market_session.jsonl
PATH="$PWD/.venv/bin:$PATH" darwin backtest --input tests/replay/multi_market_session.jsonl --output reports/backtests/sample
PATH="$PWD/.venv/bin:$PATH" darwin walk-forward --input tests/replay/multi_market_session.jsonl --output reports/walk_forward/sample
PATH="$PWD/.venv/bin:$PATH" darwin paper --markets KXTEST-YES,KXTEST-REJECT --input tests/replay/multi_market_session.jsonl --output reports/paper/sample
```

Key results: 75 tests passed; lint/typecheck passed; sample backtest net P&L `0.2374`; walk-forward aggregate net P&L `0.2374`.

## Live Paper Audit

- Audited current replay paper, WebSocket, REST, local order book, fill, accounting, CLI, and report behavior.
- Added `docs/live_paper_gap_analysis.md`.
- Verified current Kalshi docs for public orderbook REST, authenticated WebSocket handshake, public channels, orderbook snapshot/delta behavior, and lifecycle statuses.
- Next: explicit equity/closed-trade helpers, read-only market-data provider protocol, normalized event bus, mock exchange, and `darwin paper-live`.

## Live Paper Implementation

- Added explicit equity calculation and individual closed-trade P&L helpers.
- Added a read-only `MarketDataProvider` protocol and a dedicated
  `LivePaperTrader` service that depends on market data plus `PaperBroker`, not
  live execution.
- Added a bounded normalized event bus, health monitor, deterministic mock market
  data provider, SQLite normalized-event persistence, CSV/HTML session reports,
  and `darwin paper-live`.
- Added mock `markets sync` and `collect` paths that produce real metadata and
  streaming events without credentials.
- Expanded accounting, event-pipeline, mock exchange, safety-boundary, CLI, and
  live-paper integration tests. Current count: 134 tests.
- Updated README and docs for live paper trading, accounting, execution
  simulation, recovery, testing, risk, operations, and exchange integration.

Mock smoke command:

```bash
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin paper-live \
  --markets KXTEST-A,KXTEST-B \
  --duration 10 \
  --exchange-environment mock \
  --database-url sqlite:///./tmp-paper.sqlite3 \
  --output reports/paper/mock-smoke \
  --seed 42
```

Observed summary: two simulated orders, two fills, one risk rejection, nonzero
fees, nonzero realized P&L, clean shutdown, and `execution_endpoint_calls: 0`.

## Read-Only Kalshi Market Data Provider

- Re-verified current official Kalshi docs for REST/WS base URLs, public REST
  market-data endpoints, WebSocket authentication, subscription payloads,
  orderbook snapshots/deltas, public trades, market lifecycle messages,
  keepalive, errors, sequence handling, rate limits, and current V2 order
  endpoints that paper-live must not call.
- Added `KalshiMarketDataProvider`, which satisfies `MarketDataProvider` with
  only read-only methods: `list_markets`, `get_market`, `get_orderbook`,
  `stream_market_events`, and `close`.
- Strengthened Kalshi REST handling with response validation, retries,
  exponential backoff, timeout-aware logging, and a small token bucket.
- Strengthened Kalshi WebSocket handling with authenticated handshake support,
  subscription tracking, reconnect/backoff, malformed-message counts, and
  message metrics.
- Added normalized mapping for Kalshi orderbook snapshots/deltas, public trades,
  ticker metadata, lifecycle messages, sequence gaps, reconnects, and snapshot
  recovery.
- Added `paper-live --exchange-environment kalshi` and `--dry-run`. Dry-run
  maintains books and metrics while skipping strategy, risk, orders, and fills.
- Added rotated structured logs and `metrics.prom` output.
- Updated the read-only dashboard to read live-paper report directories.
- Added recorded Kalshi WebSocket fixture tests and fast stability-window tests.

Verification:

```bash
make lint
make typecheck
make test
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin paper-live --markets KXTEST-A,KXTEST-B --duration 10 --exchange-environment mock --database-url sqlite:///./tmp-paper.sqlite3 --output reports/paper/mock-smoke --seed 42
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin paper-live --markets KXBTC-YES,KXETH-YES --exchange-environment kalshi --dry-run --duration 1 --database-url sqlite:///./tmp-kalshi-dry.sqlite3 --output reports/paper/kalshi-dry
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin replay tests/replay/multi_market_session.jsonl
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin backtest --input tests/replay/multi_market_session.jsonl --output reports/backtests/sample
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin walk-forward --input tests/replay/multi_market_session.jsonl --output reports/walk_forward/sample
```

Results: Ruff passed, mypy passed, `162 passed`. Mock live paper produced two
orders, two fills, one risk rejection, nonzero fees/P&L, and
`execution_endpoint_calls: 0`. Kalshi dry-run failed closed locally because no
read-only WebSocket credentials were present.

## Kalshi Live Validation Hardening

- Re-audited Kalshi REST, WebSocket, provider selection, live-paper shutdown,
  subscription handling, sequence handling, tests, and CI.
- Added `docs/kalshi_live_validation_gap_analysis.md`.
- Split WebSocket subscriptions into a market-filtered request
  (`orderbook_delta`, `ticker`, `trade` with `market_tickers`) and a global
  lifecycle request (`market_lifecycle_v2` without ticker filters).
- Added subscription specs and acknowledgement state with request id,
  subscription id, channels, markets, creation timestamp, last-message timestamp,
  and reconnect generation.
- Replaced ad hoc sequence keys with explicit `SequenceDomain` including
  connection generation, subscription id, channel, and market ticker.
- Corrected duplicate, backward, and forward-gap semantics. Duplicates are
  dropped without recovery; backward events are health diagnostics; forward gaps
  trigger snapshot recovery.
- Reset sequence baselines on reconnect and emit normalized reconnect events.
- Refactored WebSocket reading to use the bounded raw-message queue, shutdown
  sentinels, active socket close, and interruptible reconnect backoff.
- Switched WebSocket auth timestamps to the injected clock and added deterministic
  signature tests.
- Added paginated market listing, `darwin markets list-live`, and
  `darwin validate-kalshi-feed`.
- Added dry-run validation artifacts and REST/local book validation rows.
- Replaced hardcoded execution endpoint counts with an injected
  `ExecutionEndpointGuard`.
- Updated GitHub Actions triggers and CI smoke/fixture commands.
- Added opt-in `pytest -m kalshi_live` tests that skip without credentials and
  never submit orders.

Verification:

```bash
make lint
make typecheck
make test
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin markets sync --environment mock
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin paper-live --markets KXTEST-A,KXTEST-B --exchange-environment mock --dry-run --duration 10 --output reports/paper/mock-dry
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin paper-live --markets KXTEST-A,KXTEST-B --exchange-environment mock --duration 10 --output reports/paper/mock-session
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin backtest --input tests/replay/multi_market_session.jsonl --output reports/backtests/sample
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin walk-forward --input tests/replay/multi_market_session.jsonl --output reports/walk_forward/sample
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin validate-kalshi-feed --markets KXBTC-YES,KXETH-YES --duration 1 --output reports/validation/kalshi-feed
```

Results: Ruff passed; mypy passed; `191 passed, 3 deselected`. Mock dry-run
produced validation artifacts and zero orders/fills. Mock paper session produced
two orders, two fills, one risk rejection, nonzero fees/P&L, and
`execution_endpoint_calls: 0`. Kalshi validation failed closed locally because no
WebSocket credentials were configured.

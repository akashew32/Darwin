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

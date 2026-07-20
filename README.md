# Darwin

Darwin is a safety-first prediction-market research and trading platform. It connects to exchange market data, normalizes order books, calculates microstructure features, generates inspectable momentum-biased signals, backtests event streams, supports walk-forward research, paper trades, and provides a guarded live-trading shell.

Darwin does not claim that any strategy is profitable. Reports must distinguish gross results, fees, spread costs, slippage, and realistic executable results.

## Status

Darwin is not production-ready. It now contains one replay research path and one
mock live-data paper path:

- Fully implemented: deterministic replay, local order books, incremental features,
  position-aware momentum decisions, centralized risk checks, simulated order
  lifecycle, multi-level partial fills, portfolio accounting, fees, P&L,
  event-driven backtests, walk-forward sample evaluation, mock paper trading,
  report output, read-only dashboard views over reports, mock live-data
  paper trading, bounded normalized event queues, sequence-gap recovery, and
  120+ offline tests.
- Partially implemented: real Kalshi public streaming hookup, database model
  breadth, dashboard breadth, market ranking, and statistical model training.
- Requires credentials or network: live Kalshi market-data validation and
  authenticated read-only account data.
- Intentionally disabled: real-money trading and dashboard live-order actions.
- Future work: credentialed Kalshi demo validation, richer persistence
  migrations, durable restart of live paper sessions, and production operations
  hardening.

Live trading is intentionally disabled unless every safeguard in `docs/live_trading_checklist.md` is completed.

## Setup

```bash
make setup
darwin doctor
```

If your shell cannot resolve the editable `darwin` script, prefix local commands
with `PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH"` from the repository root.

## Database

```bash
darwin db migrate
```

SQLite is the default. PostgreSQL is available through Docker Compose:

```bash
docker compose up --build
```

## Data Collection

```bash
darwin markets sync --environment mock
darwin collect --markets KXTEST-A,KXTEST-B --duration 5 --environment mock
```

Default commands are paper-safe and do not require credentials.

## Replay

```bash
darwin replay tests/replay/sample.jsonl
darwin replay tests/replay/multi_market_session.jsonl
```

## Backtesting

```bash
darwin backtest \
  --input tests/replay/multi_market_session.jsonl \
  --config config/strategies/momentum.yaml \
  --initial-cash 10000 \
  --output reports/backtests/sample
```

## Walk-Forward

```bash
darwin walk-forward \
  --input tests/replay/multi_market_session.jsonl \
  --strategy momentum \
  --config config/strategies/momentum.yaml \
  --output reports/walk_forward/sample
```

## Paper Trading

```bash
darwin paper \
  --markets KXTEST-YES,KXTEST-REJECT \
  --input tests/replay/multi_market_session.jsonl \
  --output reports/paper/sample
```

This command runs against replay/mock live data and never submits exchange orders.

## Live-Data Paper Trading

`paper-live` consumes streaming market data and simulates orders locally. The
mock environment is fully offline and is used by the test suite:

```bash
darwin paper-live \
  --markets KXTEST-A,KXTEST-B \
  --duration 10 \
  --exchange-environment mock \
  --database-url sqlite:///./tmp-paper.sqlite3 \
  --output reports/paper/mock-smoke \
  --seed 42
```

Safety boundary: `paper-live` depends on a read-only market-data protocol and a
local paper broker. The service has no dependency on the live execution broker
and the mock smoke test asserts zero exchange-order endpoint calls.

## Dashboard

```bash
darwin dashboard
```

The dashboard is read-only for live-order actions.

It reads generated report files, such as `reports/backtests/sample/summary.json`.

## Quality

```bash
make test
make lint
make typecheck
```

Current expected local result: 134 tests, Ruff clean, and strict mypy clean.

## Configuration

Environment defaults:

- `DARWIN_ENV=paper`
- `TRADING_MODE=paper`
- `KALSHI_ENV=demo`
- `DATABASE_URL=sqlite:///./darwin.sqlite3`

Credentials are optional for offline tests and paper-safe commands. Never commit `.env`, private keys, databases, raw account data, or model artifacts containing sensitive data.

## Live Trading Prerequisites

Live trading requires all of:

- `TRADING_MODE=live`
- valid Kalshi credentials
- `DARWIN_LIVE_TRADING_ACK=I_UNDERSTAND_LIVE_RISK`
- CLI `darwin live --live`
- risk config validation
- startup reconciliation
- healthy data feed
- no active kill switch
- operator review of `docs/live_trading_checklist.md`

Darwin never silently falls back from live trading to simulated trading.

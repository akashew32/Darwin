# Darwin

Darwin is a safety-first prediction-market research and trading platform. It connects to exchange market data, normalizes order books, calculates microstructure features, generates inspectable momentum-biased signals, backtests event streams, supports walk-forward research, paper trades, and provides a guarded live-trading shell.

Darwin does not claim that any strategy is profitable. Reports must distinguish gross results, fees, spread costs, slippage, and realistic executable results.

## Status

Darwin is not production-ready. It now contains one complete offline vertical path for research and paper simulation:

- Fully implemented: deterministic replay, local order books, incremental features, position-aware momentum decisions, centralized risk checks, simulated order lifecycle, multi-level partial fills, portfolio accounting, fees, P&L, event-driven backtests, walk-forward sample evaluation, mock paper trading, report output, read-only dashboard views over reports, and 75 offline tests.
- Partially implemented: Kalshi public/authenticated adapter, database model expansion, dashboard breadth, market ranking, and statistical model training.
- Requires credentials: authenticated Kalshi order/fill/position/balance verification.
- Intentionally disabled: live trading by default and dashboard live-order actions.
- Future work: full WebSocket mock-server reconnection suite, credentialed Kalshi demo validation, richer persistence migrations, and production operations hardening.

Live trading is intentionally disabled unless every safeguard in `docs/live_trading_checklist.md` is completed.

## Setup

```bash
make setup
darwin doctor
```

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
darwin markets sync
darwin collect
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

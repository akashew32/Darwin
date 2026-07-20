# Darwin

Darwin is a safety-first prediction-market research and trading platform. It connects to exchange market data, normalizes order books, calculates microstructure features, generates inspectable momentum-biased signals, backtests event streams, supports walk-forward research, paper trades, and provides a guarded live-trading shell.

Darwin does not claim that any strategy is profitable. Reports must distinguish gross results, fees, spread costs, slippage, and realistic executable results.

## Status

This repository contains the initial production-shaped implementation: typed domain models, Kalshi V2 adapter boundaries, replay/data-quality utilities, feature pipeline, baseline momentum strategy, risk engine, simulated/paper broker, portfolio accounting, event backtester, walk-forward splitter, model baselines, storage tables, CLI, API, dashboard, tests, Docker, and CI.

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
```

## Backtesting

```bash
darwin backtest
```

## Walk-Forward

```bash
darwin walk-forward
```

## Paper Trading

```bash
darwin paper
```

## Dashboard

```bash
darwin dashboard
```

The dashboard is read-only for live-order actions.

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

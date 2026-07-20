# Darwin Implementation Plan

Darwin is built as a safety-first prediction-market research and trading system. Paper trading is the default; live trading requires explicit environment variables, CLI intent, credentials, risk validation, healthy market data, reconciliation, no active kill switch, and a startup delay.

## Sequence

1. Foundation: project metadata, configuration, logging, domain models, tooling, Docker, CI, and tests.
2. Market data: Kalshi REST/WebSocket adapters, normalization, local books, persistence, replay, and quality checks.
3. Research: leakage-safe feature pipelines, ranking, transparent momentum strategy, baseline models, and reports.
4. Backtesting: event simulation using shared strategy, risk, portfolio, and order-management code.
5. Walk-forward: anchored/rolling folds, restrained optimization, out-of-sample aggregation, robustness, and sensitivity.
6. Paper trading: live-data simulation, order manager, risk engine, reconciliation, and read-only dashboard.
7. Live shell: disabled-by-default broker with all activation safeguards and operational docs.

## Kalshi Decisions Verified From Official Docs

- REST base path is `/trade-api/v2`.
- Production REST URL is `https://external-api.kalshi.com`; demo REST URL is `https://external-api.demo.kalshi.co`.
- WebSocket path is `/trade-api/ws/v2`; production host is `external-api-ws.kalshi.com`; demo host is `external-api-ws.demo.kalshi.co`.
- Authentication uses `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-SIGNATURE`, and `KALSHI-ACCESS-TIMESTAMP`.
- Signatures use RSA-PSS SHA-256 over `timestamp + method + path_without_query`.
- V2 event-market orders use fixed-point string `price` and `count` fields and `side` values `bid` or `ask`.
- Kalshi binary books expose YES bids and NO bids; opposite asks are represented internally as complementary prices.

## Current Scope

The repository provides a production-shaped platform with offline tests and mocked fixtures. Live trading is intentionally disabled unless the operator completes the checklist and enables every guard.

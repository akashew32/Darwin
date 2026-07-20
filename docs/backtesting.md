# Backtesting

Backtests are event-driven and use shared domain models, order-book reconstruction, incremental feature pipeline, strategy interface, risk engine, order manager, portfolio accounting, and simulated broker logic.

The implemented fill model walks visible book levels for marketable orders, supports partial fills, limits participation in displayed depth, and records fees, spread cost, and slippage. Passive queue reconstruction remains a documented limitation unless richer public trade data is available.

Reports must separate gross, fees, spread cost, slippage, and net results.

Sample command:

```bash
darwin backtest --input tests/replay/multi_market_session.jsonl --output reports/backtests/sample
```

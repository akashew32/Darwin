# Operations

Use `darwin doctor` before running services. Use `darwin kill` to activate the persistent kill switch. Use `darwin status` to inspect mode and kill-switch state.

Docker Compose starts PostgreSQL and the API service for local development.

Local verification:

```bash
make lint
make typecheck
make test
darwin replay tests/replay/multi_market_session.jsonl
darwin backtest --input tests/replay/multi_market_session.jsonl --output reports/backtests/sample
darwin walk-forward --input tests/replay/multi_market_session.jsonl --output reports/walk_forward/sample
darwin paper --markets KXTEST-YES,KXTEST-REJECT --input tests/replay/multi_market_session.jsonl --output reports/paper/sample
```

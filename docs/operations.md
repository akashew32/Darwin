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
darwin markets sync --environment mock
darwin collect --markets KXTEST-A,KXTEST-B --duration 5 --environment mock
darwin paper-live --markets KXTEST-A,KXTEST-B --duration 10 --exchange-environment mock --database-url sqlite:///./tmp-paper.sqlite3 --output reports/paper/mock-smoke --seed 42
```

`paper-live` prints a paper-only safety banner and reports
`execution_endpoint_calls: 0` in the mock smoke summary.

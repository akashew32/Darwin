# Final Verification

Verified on 2026-07-20 in `/Users/aakashjha/Documents/New project/Darwin`.

## Commands Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
PATH="$PWD/.venv/bin:$PATH" make lint
PATH="$PWD/.venv/bin:$PATH" make typecheck
PATH="$PWD/.venv/bin:$PATH" make test
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin doctor
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin db migrate
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin markets sync --environment mock
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin collect --markets KXTEST-A,KXTEST-B --duration 5 --environment mock
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin replay tests/replay/multi_market_session.jsonl
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin backtest --input tests/replay/multi_market_session.jsonl --output reports/backtests/sample
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin walk-forward --input tests/replay/multi_market_session.jsonl --output reports/walk_forward/sample
PYTHONPATH=src PATH="$PWD/.venv/bin:$PATH" darwin paper-live --markets KXTEST-A,KXTEST-B --duration 10 --exchange-environment mock --database-url sqlite:///./tmp-paper.sqlite3 --output reports/paper/mock-smoke --seed 42
```

## Results

- Tests: `134 passed`.
- Tests after Kalshi read-only market-data phase: `162 passed`.
- Tests after Kalshi live-validation hardening: `191 passed, 3 deselected`.
- Lint: `All checks passed`.
- Format: `134 files already formatted`.
- Typecheck after hardening: `Success: no issues found in 95 source files`.
- Doctor: paper defaults, database config, kill switch, and live guard checks passed.
- Database migration: SQLite tables created.
- Market sync: wrote 2 mock markets.
- Collect: collected 5 mock events.
- Replay: deterministic multi-market replay read `6` events.
- Backtest: `net_pnl=0.2374`, `fill_count=2`, `order_count=2`, `fees=0.0006`, `spread_cost=0.042`.
- Walk-forward: `fold_count=1`, `aggregate_net_pnl=0.2374`, `robustness_score=0.98`.
- Mock live paper: `orders=2`, `fills=2`, `risk_rejections=1`, `fees=0.0004`, `realized_pnl=0.1188`, `execution_endpoint_calls=0`.
- Kalshi dry-run without credentials: failed closed with
  `Kalshi WebSocket market data requires KALSHI_API_KEY_ID and a private key`.
- Mock dry-run validation artifacts generated: `connection_summary.json`,
  `subscriptions.json`, `market_health.csv`, `sequence_events.csv`,
  `received_message_types.csv`, `orderbook_validation.csv`, `metrics.prom`, and
  `dry_run_report.html`.

## Notes

- Dependencies were installed into a local `.venv` because the user-level Python site-packages directory was not writable.
- No credentials, private keys, account data, databases, or model artifacts are committed.
- Live trading remains intentionally disabled behind explicit safeguards.
- Real Kalshi market-data streaming still requires network and, where applicable,
  read-only credential validation.

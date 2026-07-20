# Final Verification

Verified on 2026-07-20 in `/Users/aakashjha/Documents/New project/Darwin`.

## Commands Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
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

## Results

- Tests: `75 passed`.
- Lint: `All checks passed`.
- Format: `112 files already formatted`.
- Typecheck: `Success: no issues found in 84 source files`.
- Doctor: paper defaults, database config, kill switch, and live guard checks passed.
- Database migration: SQLite tables created.
- Replay: deterministic multi-market replay read `6` events.
- Backtest: `net_pnl=0.2374`, `fill_count=2`, `order_count=2`, `fees=0.0006`, `spread_cost=0.042`.
- Walk-forward: `fold_count=1`, `aggregate_net_pnl=0.2374`, `robustness_score=0.97741`.
- Mock paper: same deterministic paper summary as sample backtest; no live orders submitted.

## Notes

- Dependencies were installed into a local `.venv` because the user-level Python site-packages directory was not writable.
- No credentials, private keys, account data, databases, or model artifacts are committed.
- Live trading remains intentionally disabled behind explicit safeguards.

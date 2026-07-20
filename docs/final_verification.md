# Final Verification

Verified on 2026-07-20 in `/Users/aakashjha/Documents/New project/Darwin`.

## Commands Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy
.venv/bin/darwin doctor
.venv/bin/darwin replay tests/replay/sample.jsonl
```

## Results

- Tests: `10 passed`.
- Lint: `All checks passed`.
- Format: `99 files already formatted`.
- Typecheck: `Success: no issues found in 83 source files`.
- Doctor: paper defaults, database config, kill switch, and live guard checks passed.
- Replay: deterministic sample replay read `1` event.

## Notes

- Dependencies were installed into a local `.venv` because the user-level Python site-packages directory was not writable.
- No credentials, private keys, account data, databases, or model artifacts are committed.
- Live trading remains intentionally disabled behind explicit safeguards.

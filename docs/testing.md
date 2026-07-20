# Testing

The default suite requires no credentials and no external network.

```bash
make lint
make typecheck
make test
```

Current expected result:

- 162 tests passing
- Ruff lint and format passing
- strict mypy passing for `src/darwin`

Important integration checks:

```bash
darwin markets sync --environment mock
darwin collect --markets KXTEST-A,KXTEST-B --duration 5 --environment mock
darwin paper-live \
  --markets KXTEST-A,KXTEST-B \
  --duration 10 \
  --exchange-environment mock \
  --database-url sqlite:///./tmp-paper.sqlite3 \
  --output reports/paper/mock-smoke \
  --seed 42
```

The mock smoke test verifies initial snapshots, streaming events, a sequence gap,
snapshot recovery, reconnect handling, a risk rejection, simulated fills,
portfolio updates, nonzero fees, report output, and zero exchange-order endpoint
calls.

Recorded Kalshi fixture tests normalize documented WebSocket orderbook,
trade, ticker, lifecycle, duplicate, and sequence-gap messages without network
or credentials.

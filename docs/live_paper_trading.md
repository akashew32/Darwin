# Live Paper Trading

`darwin paper-live` is for real or mock market data with local-only simulated
orders. It is intentionally separate from real-money execution.

```bash
darwin paper-live \
  --markets KXTEST-A,KXTEST-B \
  --duration 10 \
  --exchange-environment mock \
  --database-url sqlite:///./tmp-paper.sqlite3 \
  --output reports/paper/mock-smoke \
  --seed 42
```

The command currently supports the deterministic `mock` environment. The service
loads initial snapshots before processing deltas, maintains local books, computes
stateful features, asks the momentum strategy for structured decisions, sends
every proposed order through `RiskEngine`, simulates fills with `PaperBroker`,
updates the portfolio, persists normalized events, and writes CSV plus HTML
session output.

Safety boundary:

- The live-paper service accepts only `MarketDataProvider`.
- `MarketDataProvider` exposes read-only market-data methods.
- The service owns a local `PaperBroker`.
- It does not import or receive a live execution broker.
- Paper tests assert that submit, amend, and cancel exchange endpoints are not
  reachable from this path.

Current limitations:

- The real Kalshi streaming environment still requires network validation.
- Durable `--resume` is acknowledged but the mock path starts a fresh session.
- Persistence is intentionally narrow SQLite session state for live-paper smoke
  runs, not the full production schema.

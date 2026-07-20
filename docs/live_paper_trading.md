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

The command supports the deterministic `mock` environment and a read-only
`kalshi` market-data environment. Kalshi streaming requires API-key credentials
for the signed WebSocket handshake, but paper-live never sends exchange orders.
The service loads initial REST snapshots before processing deltas, maintains
local books, computes stateful features, asks the momentum strategy for
structured decisions, sends every proposed order through `RiskEngine`, simulates
fills with `PaperBroker`, updates the portfolio, persists normalized events, and
writes CSV plus HTML session output.

Kalshi dry-run mode validates market-data connectivity without strategy, risk,
orders, or fills:

```bash
darwin paper-live \
  --markets KXBTC-YES,KXETH-YES \
  --exchange-environment kalshi \
  --dry-run
```

Safety boundary:

- The live-paper service accepts only `MarketDataProvider`.
- `MarketDataProvider` exposes only read-only market-data methods.
- The service owns a local `PaperBroker`.
- It does not import or receive a live execution broker.
- Paper tests assert that submit, amend, and cancel exchange endpoints are not
  reachable from this path.

Current limitations:

- The real Kalshi streaming environment requires operator-provided read-only
  WebSocket credentials and network access.
- Durable `--resume` is acknowledged but the mock path starts a fresh session.
- Persistence is intentionally narrow SQLite session state for live-paper smoke
  runs, not the full production schema.

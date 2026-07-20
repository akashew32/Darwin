# Agent Instructions For Darwin

- Paper trading is the default. Do not make live trading easier to start.
- Keep exchange-specific code under `src/darwin/exchanges/*`.
- Strategies, risk, portfolio, accounting, and backtests must consume Darwin domain models, not raw exchange payloads.
- Verify exchange endpoint paths, auth, field names, and WebSocket schemas against official docs before changing adapters.
- Never commit credentials, private keys, `.env`, account data, raw private data, or sensitive model artifacts.
- Use `Decimal` or integer units for prices, cash, fees, and order accounting.
- Run `make test`, `make lint`, and `make typecheck` before shipping substantial changes.
- Tests must pass without network access or live credentials.
- Orders must pass through the centralized risk engine before execution.
- Keep dashboard live-order actions read-only unless a future reviewed release explicitly changes that.

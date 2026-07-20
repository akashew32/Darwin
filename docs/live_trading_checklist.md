# Live Trading Checklist

Complete every item before enabling real capital:

- Review current Kalshi API documentation.
- Confirm credentials are loaded from environment or private key path only.
- Set `TRADING_MODE=live`.
- Set `DARWIN_LIVE_TRADING_ACK=I_UNDERSTAND_LIVE_RISK`.
- Use `darwin live --live`.
- Verify risk limits are conservative and complete.
- Confirm database migrations are current.
- Run startup reconciliation.
- Confirm WebSocket feed health and data freshness.
- Confirm no active kill switch.
- Confirm paper trading has run end to end with the same configuration.
- Confirm cancel-all works in authenticated test mode.
- Confirm operator monitoring is staffed.

Do not enable live trading from the dashboard.

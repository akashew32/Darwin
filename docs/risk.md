# Risk

Every order proposal must pass through `RiskEngine`.

Implemented checks include kill switch, duplicate client order ID, order size, market position, gross exposure, true open-order count, available cash, order notional, spread, market-data age, slippage, minimum net edge, depth participation, market status, fat-finger prices, feed health, database health, position mismatch, exchange error circuit breaker, rejection circuit breaker, daily loss, and drawdown.

The kill switch is persistent and stops new submissions. It does not automatically liquidate positions during infrastructure failure.

Live paper trading also passes feed health into the risk context. New entries are
rejected when the book is recovering, market data is stale, queue pressure is
unsafe, or the database/feed health flags are false. Rejection rows include all
reasons returned by the engine so reports can distinguish strategy holds from
risk blocks.

Risk thresholds are configuration values in `RiskConfig`; hardcoded spread,
slippage, loss, drawdown, queue, reconnect, and stale-data limits should not be
introduced in trading paths.

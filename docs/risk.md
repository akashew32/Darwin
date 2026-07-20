# Risk

Every order proposal must pass through `RiskEngine`.

Implemented checks include kill switch, duplicate client order ID, order size, market position, gross exposure, true open-order count, available cash, order notional, spread, market-data age, slippage, minimum net edge, depth participation, market status, fat-finger prices, feed health, database health, position mismatch, exchange error circuit breaker, rejection circuit breaker, daily loss, and drawdown.

The kill switch is persistent and stops new submissions. It does not automatically liquidate positions during infrastructure failure.

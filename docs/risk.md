# Risk

Every order proposal must pass through `RiskEngine`.

Implemented checks include kill switch, duplicate client order ID, order size, gross exposure, open-order count, spread, market-data age, minimum cash, and minimum edge.

The kill switch is persistent and stops new submissions. It does not automatically liquidate positions during infrastructure failure.

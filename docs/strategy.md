# Strategy

The initial strategy is a liquidity-filtered momentum baseline with order-book confirmation. It is intended to be inspectable, not proof of alpha.

Decisions combine momentum, book imbalance, trade-flow imbalance, breakout strength, spread penalty, volatility penalty, and staleness penalty. Entry requires sufficient depth, acceptable spread, fresh data, and expected net edge above costs and buffers.

The strategy is position-aware. It exits on stop-loss, take-profit, momentum reversal, and avoids duplicate entry when an equivalent order is open. It emits structured decisions with proposed orders, fair value, executable price, fees, slippage, gross edge, and net edge.

Known risks include overfitting, stale data, spread widening, incomplete queue information, market halts, resolution ambiguity, and logically related market exposure.

The strategy should stop trading when market data is stale, spreads widen beyond limits, the kill switch is active, position reconciliation fails, daily loss limits are hit, or market status is not open.

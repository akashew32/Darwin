# Strategy

The initial strategy is a liquidity-filtered momentum baseline with order-book confirmation. It is intended to be inspectable, not proof of alpha.

Signals combine momentum, book imbalance, trade-flow imbalance, breakout strength, spread penalty, volatility penalty, and staleness penalty. Entry requires sufficient depth, acceptable spread, fresh data, and expected edge above costs and buffers.

Known risks include overfitting, stale data, spread widening, incomplete queue information, market halts, resolution ambiguity, and logically related market exposure.

The strategy should stop trading when market data is stale, spreads widen beyond limits, the kill switch is active, position reconciliation fails, daily loss limits are hit, or market status is not open.

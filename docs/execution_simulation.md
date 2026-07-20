# Execution Simulation

Backtests, replay paper trading, and live-data paper trading use simulated
execution. No paper path submits exchange orders.

Configurable execution inputs are represented by `ExecutionSimulationConfig`:

- fill model name
- submission latency
- cancellation latency
- exchange and network latency assumptions
- slippage basis points
- maximum displayed-depth participation
- random seed
- order expiration and repricing intervals

Marketable fills walk the visible book and may partially fill when configured
participation or displayed liquidity is insufficient. Slippage is applied to the
executed price. Passive-order support is conservative: a touch does not imply a
fill, because public data cannot reveal exact queue position.

The current live-paper mock path uses deterministic marketable fills so the smoke
test is reproducible and demonstrates a partial fill, an exit, a risk rejection,
nonzero fees, and clean shutdown.

# Backtesting

Backtests are event-driven and use shared domain models, feature pipeline, strategy interface, risk engine, portfolio accounting, and simulated broker logic.

The fill model is conservative: touched orders are not assumed to fill in all future extensions; the initial implementation supports immediate execution against visible top-of-book when marketable.

Reports must separate gross, fees, spread cost, slippage, and net results.

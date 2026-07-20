# Accounting

Darwin uses `Decimal` for money-like values and never uses binary floating point
for order accounting.

Equity is calculated by `calculate_equity(portfolio, market_marks, open_orders)`:

```text
equity =
  cash
  + reserved_cash
  + marked YES position value
  + marked NO position value
```

Open order reserves are included when passed to the function. Current portfolio
cash is already net of executed fill notional and fees, so realized P&L and fees
are tracked for reporting rather than added a second time to equity.

Closed-trade P&L is produced at the fill that reduces or closes exposure. Metrics
use the individual closed lot or exit transaction, not cumulative portfolio
realized P&L snapshots. Duplicate fill IDs are idempotent.

Test coverage includes open YES/NO valuation, partial reduction, full close,
reversal, settlement, duplicate fills, late fills, multiple fill prices, fees,
cash reserve release, equity mark updates, and replay reconstruction.

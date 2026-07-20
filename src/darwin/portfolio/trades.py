from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from darwin.domain.enums import OutcomeSide


@dataclass(frozen=True)
class ClosedTrade:
    entry_ts: datetime
    exit_ts: datetime
    market_id: str
    outcome: OutcomeSide
    quantity: int
    average_entry_price: Decimal
    average_exit_price: Decimal
    gross_realized_pnl: Decimal
    fees: Decimal
    slippage: Decimal
    net_realized_pnl: Decimal
    holding_seconds: float
    exit_reason: str

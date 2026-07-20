from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from darwin.domain.position import Position


class PortfolioState(BaseModel):
    model_config = ConfigDict(frozen=True)

    cash: Decimal
    reserved_cash: Decimal = Decimal("0")
    positions: dict[str, Position] = Field(default_factory=dict)
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")

    @property
    def available_cash(self) -> Decimal:
        return self.cash - self.reserved_cash

    @property
    def gross_contracts(self) -> int:
        return sum(abs(p.yes_quantity) + abs(p.no_quantity) for p in self.positions.values())

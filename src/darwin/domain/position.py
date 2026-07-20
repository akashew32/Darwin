from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Position(BaseModel):
    model_config = ConfigDict(frozen=True)

    market_id: str
    yes_quantity: int = 0
    no_quantity: int = 0
    average_yes_cost: Decimal = Decimal("0")
    average_no_cost: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    seen_fill_ids: frozenset[str] = Field(default_factory=frozenset)
    settled: bool = False

    @property
    def net_yes_exposure(self) -> int:
        return self.yes_quantity - self.no_quantity

    def mark_unrealized(self, yes_mark: Decimal) -> Decimal:
        no_mark = Decimal("1") - yes_mark
        return Decimal(self.yes_quantity) * (yes_mark - self.average_yes_cost) + Decimal(
            self.no_quantity
        ) * (no_mark - self.average_no_cost)

    @property
    def gross_exposure(self) -> Decimal:
        return Decimal(abs(self.yes_quantity) + abs(self.no_quantity))

    @property
    def worst_case_loss(self) -> Decimal:
        yes_loss = Decimal(self.yes_quantity) * self.average_yes_cost
        no_loss = Decimal(self.no_quantity) * self.average_no_cost
        return max(Decimal("0"), yes_loss + no_loss)

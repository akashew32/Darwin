from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from darwin.domain.enums import Exchange, MarketStatus, OutcomeSide


class Outcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    side: OutcomeSide
    label: str


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    exchange: Exchange
    event_id: str
    title: str
    category: str | None = None
    close_time: datetime | None = None


class Market(BaseModel):
    model_config = ConfigDict(frozen=True)

    exchange: Exchange
    market_id: str
    event_id: str
    title: str
    status: MarketStatus
    outcomes: tuple[Outcome, ...] = Field(default_factory=tuple)
    close_time: datetime | None = None
    category: str | None = None
    min_price: Decimal = Decimal("0.01")
    max_price: Decimal = Decimal("0.99")
    tick_size: Decimal = Decimal("0.01")

    @field_validator("min_price", "max_price", "tick_size")
    @classmethod
    def _positive_probability(cls, value: Decimal) -> Decimal:
        if value <= 0 or value >= 1:
            raise ValueError("market price bounds must be inside (0, 1)")
        return value

    @model_validator(mode="after")
    def _valid_bounds(self) -> "Market":
        if self.min_price >= self.max_price:
            raise ValueError("min_price must be below max_price")
        return self

    @property
    def accepts_orders(self) -> bool:
        return self.status == MarketStatus.OPEN

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from darwin.constants import PROBABILITY_MAX, PROBABILITY_MIN
from darwin.domain.enums import BookSide, Exchange, OutcomeSide


class PriceLevel(BaseModel):
    model_config = ConfigDict(frozen=True)

    price: Decimal
    quantity: int

    @field_validator("price")
    @classmethod
    def _probability(cls, value: Decimal) -> Decimal:
        if not (PROBABILITY_MIN <= value <= PROBABILITY_MAX):
            raise ValueError("price must be a probability in [0, 1]")
        return value

    @field_validator("quantity")
    @classmethod
    def _positive_quantity(cls, value: int) -> int:
        if value < 0:
            raise ValueError("quantity cannot be negative")
        return value


class OrderBookSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    exchange: Exchange
    market_id: str
    outcome: OutcomeSide = OutcomeSide.YES
    bids: tuple[PriceLevel, ...] = Field(default_factory=tuple)
    asks: tuple[PriceLevel, ...] = Field(default_factory=tuple)
    sequence: int | None = None
    exchange_ts: datetime | None = None
    received_ts: datetime

    @model_validator(mode="after")
    def _valid_book(self) -> "OrderBookSnapshot":
        if any(a.price <= b.price for b in self.bids for a in self.asks):
            raise ValueError("book is crossed")
        if list(self.bids) != sorted(self.bids, key=lambda x: x.price, reverse=True):
            raise ValueError("bids must be sorted high to low")
        if list(self.asks) != sorted(self.asks, key=lambda x: x.price):
            raise ValueError("asks must be sorted low to high")
        return self

    @property
    def best_bid(self) -> Decimal | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return self.asks[0].price if self.asks else None

    @property
    def midprice(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / Decimal("2")


class OrderBookDelta(BaseModel):
    model_config = ConfigDict(frozen=True)

    exchange: Exchange
    market_id: str
    side: BookSide
    outcome: OutcomeSide
    price: Decimal
    delta_quantity: int
    absolute_quantity: int | None = None
    sequence: int | None = None
    exchange_ts: datetime | None = None
    received_ts: datetime

    @field_validator("price")
    @classmethod
    def _probability(cls, value: Decimal) -> Decimal:
        if not (PROBABILITY_MIN <= value <= PROBABILITY_MAX):
            raise ValueError("price must be a probability in [0, 1]")
        return value

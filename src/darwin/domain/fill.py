from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from darwin.constants import PROBABILITY_MAX, PROBABILITY_MIN
from darwin.domain.enums import Exchange, OrderIntent, OutcomeSide


class Fill(BaseModel):
    model_config = ConfigDict(frozen=True)

    exchange: Exchange
    fill_id: str
    market_id: str
    client_order_id: str
    exchange_order_id: str | None = None
    outcome: OutcomeSide
    intent: OrderIntent
    price: Decimal
    quantity: int
    fee: Decimal = Decimal("0")
    exchange_ts: datetime | None = None
    received_ts: datetime

    @field_validator("price")
    @classmethod
    def _price(cls, value: Decimal) -> Decimal:
        if not (PROBABILITY_MIN < value < PROBABILITY_MAX):
            raise ValueError("fill price must be inside (0, 1)")
        return value

    @field_validator("quantity")
    @classmethod
    def _quantity(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("fill quantity must be positive")
        return value

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from darwin.constants import PROBABILITY_MAX, PROBABILITY_MIN
from darwin.domain.enums import Exchange, OrderIntent, OrderStatus, OutcomeSide
from darwin.domain.market import Market


class OrderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    exchange: Exchange
    market_id: str
    outcome: OutcomeSide
    intent: OrderIntent
    limit_price: Decimal
    quantity: int
    client_order_id: str
    post_only: bool = True
    created_ts: datetime

    @field_validator("limit_price")
    @classmethod
    def _price(cls, value: Decimal) -> Decimal:
        if not (PROBABILITY_MIN < value < PROBABILITY_MAX):
            raise ValueError("limit price must be inside (0, 1)")
        return value

    @field_validator("quantity")
    @classmethod
    def _quantity(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("quantity must be positive")
        return value

    def validate_market(self, market: Market) -> None:
        if not market.accepts_orders:
            raise ValueError("market does not accept new orders")
        if self.limit_price < market.min_price or self.limit_price > market.max_price:
            raise ValueError("limit price outside venue bounds")


class Order(BaseModel):
    model_config = ConfigDict(frozen=True)

    request: OrderRequest
    status: OrderStatus
    remaining_quantity: int
    filled_quantity: int = 0
    average_fill_price: Decimal | None = None
    fees: Decimal = Decimal("0")
    exchange_order_id: str | None = None
    created_ts: datetime
    updated_ts: datetime
    exchange_ts: datetime | None = None
    rejection_reason: str | None = None
    cancellation_reason: str | None = None

    @model_validator(mode="after")
    def _quantities(self) -> "Order":
        if self.filled_quantity < 0 or self.remaining_quantity < 0:
            raise ValueError("order quantities cannot be negative")
        if self.filled_quantity > self.request.quantity:
            raise ValueError("filled quantity cannot exceed submitted quantity")
        if self.filled_quantity + self.remaining_quantity > self.request.quantity:
            raise ValueError("filled plus remaining exceeds submitted quantity")
        return self

    @classmethod
    def created(cls, request: OrderRequest) -> "Order":
        return cls(
            request=request,
            status=OrderStatus.CREATED,
            remaining_quantity=request.quantity,
            created_ts=request.created_ts,
            updated_ts=request.created_ts,
        )

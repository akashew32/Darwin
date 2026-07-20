from datetime import datetime
from decimal import Decimal

from darwin.domain.enums import OrderStatus
from darwin.domain.fill import Fill
from darwin.domain.order import Order

TERMINAL = {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.EXPIRED}


def acknowledge(order: Order, exchange_order_id: str, ts: datetime) -> Order:
    if order.status in TERMINAL:
        return order
    return order.model_copy(
        update={
            "status": OrderStatus.ACKNOWLEDGED,
            "exchange_order_id": exchange_order_id,
            "updated_ts": ts,
        }
    )


def apply_fill(order: Order, fill: Fill) -> Order:
    if order.status in {OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.EXPIRED}:
        return order
    applied_quantity = min(order.remaining_quantity, fill.quantity)
    if applied_quantity <= 0:
        return order
    new_filled = order.filled_quantity + applied_quantity
    remaining = max(0, order.request.quantity - new_filled)
    previous_notional = (order.average_fill_price or Decimal("0")) * Decimal(order.filled_quantity)
    fill_notional = fill.price * Decimal(applied_quantity)
    avg = (previous_notional + fill_notional) / Decimal(new_filled)
    status = OrderStatus.FILLED if remaining == 0 else OrderStatus.PARTIALLY_FILLED
    return order.model_copy(
        update={
            "status": status,
            "filled_quantity": new_filled,
            "remaining_quantity": remaining,
            "average_fill_price": avg,
            "fees": order.fees + fill.fee,
            "updated_ts": fill.received_ts,
        }
    )


def cancel(order: Order, ts: datetime, reason: str) -> Order:
    if order.status in TERMINAL:
        return order
    return order.model_copy(
        update={
            "status": OrderStatus.CANCELED,
            "remaining_quantity": 0,
            "updated_ts": ts,
            "cancellation_reason": reason,
        }
    )


def reject(order: Order, ts: datetime, reason: str) -> Order:
    if order.status in TERMINAL:
        return order
    return order.model_copy(
        update={
            "status": OrderStatus.REJECTED,
            "remaining_quantity": 0,
            "updated_ts": ts,
            "rejection_reason": reason,
        }
    )

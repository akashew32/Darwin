from dataclasses import dataclass
from datetime import datetime

from darwin.domain.enums import OrderStatus
from darwin.domain.fill import Fill
from darwin.domain.order import Order, OrderRequest
from darwin.execution.state_machine import TERMINAL, acknowledge, apply_fill, cancel, reject


@dataclass(frozen=True)
class OrderTransition:
    client_order_id: str
    previous: OrderStatus
    new: OrderStatus
    reason: str
    event_ts: datetime
    received_ts: datetime
    correlation_id: str


class OrderManager:
    def __init__(self) -> None:
        self.orders: dict[str, Order] = {}
        self.transitions: list[OrderTransition] = []
        self.seen_fill_ids: set[str] = set()

    def create(self, request: OrderRequest, correlation_id: str = "local") -> Order:
        if request.client_order_id in self.orders:
            return self.orders[request.client_order_id]
        order = Order.created(request)
        self.orders[request.client_order_id] = order
        self._record(
            order,
            OrderStatus.CREATED,
            "created",
            request.created_ts,
            request.created_ts,
            correlation_id,
        )
        return order

    def acknowledge(
        self,
        client_order_id: str,
        exchange_order_id: str,
        ts: datetime,
        correlation_id: str = "ack",
    ) -> Order:
        order = self.orders[client_order_id]
        updated = acknowledge(order, exchange_order_id, ts)
        self._update(order, updated, "acknowledged", ts, ts, correlation_id)
        return updated

    def apply_fill(self, fill: Fill, correlation_id: str = "fill") -> Order | None:
        if fill.fill_id in self.seen_fill_ids:
            return self.orders.get(fill.client_order_id)
        order = self.orders.get(fill.client_order_id)
        if order is None:
            return None
        self.seen_fill_ids.add(fill.fill_id)
        updated = apply_fill(order, fill)
        self._update(
            order,
            updated,
            "fill",
            fill.exchange_ts or fill.received_ts,
            fill.received_ts,
            correlation_id,
        )
        return updated

    def cancel(self, client_order_id: str, ts: datetime, reason: str = "cancel") -> Order:
        order = self.orders[client_order_id]
        updated = cancel(order, ts, reason)
        self._update(order, updated, reason, ts, ts, "cancel")
        return updated

    def reject(self, client_order_id: str, ts: datetime, reason: str) -> Order:
        order = self.orders[client_order_id]
        updated = reject(order, ts, reason)
        self._update(order, updated, reason, ts, ts, "reject")
        return updated

    def open_orders(self) -> list[Order]:
        return [order for order in self.orders.values() if order.status not in TERMINAL]

    def _update(
        self,
        old: Order,
        new: Order,
        reason: str,
        event_ts: datetime,
        received_ts: datetime,
        correlation_id: str,
    ) -> None:
        self.orders[new.request.client_order_id] = new
        if old.status != new.status:
            self._record(new, old.status, reason, event_ts, received_ts, correlation_id)

    def _record(
        self,
        order: Order,
        previous: OrderStatus,
        reason: str,
        event_ts: datetime,
        received_ts: datetime,
        correlation_id: str,
    ) -> None:
        self.transitions.append(
            OrderTransition(
                client_order_id=order.request.client_order_id,
                previous=previous,
                new=order.status,
                reason=reason,
                event_ts=event_ts,
                received_ts=received_ts,
                correlation_id=correlation_id,
            )
        )

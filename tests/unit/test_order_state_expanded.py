from datetime import UTC, datetime
from decimal import Decimal

import pytest

from darwin.domain.enums import Exchange, OrderIntent, OrderStatus, OutcomeSide
from darwin.domain.fill import Fill
from darwin.domain.order import Order, OrderRequest
from darwin.execution.client_order_id import ClientOrderIdFactory
from darwin.execution.order_manager import OrderManager
from darwin.execution.state_machine import apply_fill, cancel, reject


def request(client_id: str = "c", quantity: int = 5) -> OrderRequest:
    return OrderRequest(
        exchange=Exchange.KALSHI,
        market_id="M",
        outcome=OutcomeSide.YES,
        intent=OrderIntent.BUY,
        limit_price=Decimal("0.50"),
        quantity=quantity,
        client_order_id=client_id,
        created_ts=datetime.now(UTC),
    )


def fill(fill_id: str, quantity: int) -> Fill:
    return Fill(
        exchange=Exchange.KALSHI,
        fill_id=fill_id,
        market_id="M",
        client_order_id="c",
        outcome=OutcomeSide.YES,
        intent=OrderIntent.BUY,
        price=Decimal("0.50"),
        quantity=quantity,
        received_ts=datetime.now(UTC),
    )


@pytest.mark.parametrize(
    "quantity,status",
    [(1, OrderStatus.PARTIALLY_FILLED), (5, OrderStatus.FILLED), (9, OrderStatus.FILLED)],
)
def test_apply_fill_caps_quantity(quantity: int, status: OrderStatus) -> None:
    updated = apply_fill(Order.created(request()), fill("f", quantity))
    assert updated.filled_quantity <= 5
    assert updated.status == status


@pytest.mark.parametrize("transition", ["cancel", "reject"])
def test_terminal_transitions(transition: str) -> None:
    order = Order.created(request())
    updated = (
        cancel(order, datetime.now(UTC), "operator")
        if transition == "cancel"
        else reject(order, datetime.now(UTC), "bad")
    )
    assert updated.status in {OrderStatus.CANCELED, OrderStatus.REJECTED}
    assert updated.remaining_quantity == 0


def test_order_manager_duplicate_fill_idempotent() -> None:
    manager = OrderManager()
    manager.create(request())
    first = manager.apply_fill(fill("f", 2))
    second = manager.apply_fill(fill("f", 2))
    assert first == second
    assert len(manager.transitions) == 2


def test_client_order_ids_do_not_collide_same_second() -> None:
    factory = ClientOrderIdFactory("s")
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    ids = {factory.next("M", ts, "enter") for _ in range(20)}
    assert len(ids) == 20

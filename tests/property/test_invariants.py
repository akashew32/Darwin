from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from darwin.domain.enums import Exchange, OrderIntent, OutcomeSide
from darwin.domain.fill import Fill
from darwin.domain.order import Order, OrderRequest
from darwin.execution.state_machine import apply_fill


@given(
    quantity=st.integers(min_value=1, max_value=100),
    fill_qty=st.integers(min_value=1, max_value=100),
)
def test_fills_never_exceed_order_quantity(quantity: int, fill_qty: int) -> None:
    now = datetime.now(UTC)
    request = OrderRequest(
        exchange=Exchange.KALSHI,
        market_id="M",
        outcome=OutcomeSide.YES,
        intent=OrderIntent.BUY,
        limit_price=Decimal("0.5"),
        quantity=quantity,
        client_order_id="c",
        created_ts=now,
    )
    order = Order.created(request)
    fill = Fill(
        exchange=Exchange.KALSHI,
        fill_id="f",
        market_id="M",
        client_order_id="c",
        outcome=OutcomeSide.YES,
        intent=OrderIntent.BUY,
        price=Decimal("0.5"),
        quantity=fill_qty,
        received_ts=now,
    )
    updated = apply_fill(order, fill)
    assert updated.filled_quantity <= quantity
    assert updated.remaining_quantity >= 0

from datetime import UTC, datetime
from decimal import Decimal

from darwin.domain.enums import Exchange, OrderIntent, OutcomeSide
from darwin.domain.order import OrderRequest
from darwin.domain.orderbook import OrderBookSnapshot, PriceLevel
from darwin.execution.simulated_broker import SimulatedBroker


def snapshot() -> OrderBookSnapshot:
    return OrderBookSnapshot(
        exchange=Exchange.KALSHI,
        market_id="M",
        bids=(PriceLevel(price=Decimal("0.49"), quantity=10),),
        asks=(
            PriceLevel(price=Decimal("0.51"), quantity=4),
            PriceLevel(price=Decimal("0.52"), quantity=4),
        ),
        received_ts=datetime.now(UTC),
    )


def request(quantity: int, price: str = "0.52") -> OrderRequest:
    return OrderRequest(
        exchange=Exchange.KALSHI,
        market_id="M",
        outcome=OutcomeSide.YES,
        intent=OrderIntent.BUY,
        limit_price=Decimal(price),
        quantity=quantity,
        client_order_id=f"c-{quantity}-{price}",
        created_ts=datetime.now(UTC),
    )


def test_multi_level_partial_fill() -> None:
    result = SimulatedBroker().submit_against_snapshot(request(5), snapshot(), datetime.now(UTC))
    assert result.order.filled_quantity == 4
    assert result.missed_quantity == 1
    assert len(result.fills) == 2


def test_limit_prevents_fill() -> None:
    result = SimulatedBroker().submit_against_snapshot(
        request(5, "0.50"), snapshot(), datetime.now(UTC)
    )
    assert result.order.filled_quantity == 0
    assert result.fills == ()


def test_slippage_changes_price() -> None:
    result = SimulatedBroker().submit_against_snapshot(
        request(1), snapshot(), datetime.now(UTC), slippage_bps=10
    )
    assert result.fills[0].price > Decimal("0.51")

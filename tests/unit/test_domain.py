from datetime import UTC, datetime
from decimal import Decimal

import pytest

from darwin.domain.enums import Exchange, OrderIntent, OutcomeSide
from darwin.domain.order import OrderRequest
from darwin.domain.orderbook import OrderBookSnapshot, PriceLevel


def test_order_request_requires_positive_quantity() -> None:
    with pytest.raises(ValueError):
        OrderRequest(
            exchange=Exchange.KALSHI,
            market_id="M",
            outcome=OutcomeSide.YES,
            intent=OrderIntent.BUY,
            limit_price=Decimal("0.5"),
            quantity=0,
            client_order_id="c",
            created_ts=datetime.now(UTC),
        )


def test_orderbook_rejects_crossed_book() -> None:
    with pytest.raises(ValueError):
        OrderBookSnapshot(
            exchange=Exchange.KALSHI,
            market_id="M",
            bids=(PriceLevel(price=Decimal("0.55"), quantity=10),),
            asks=(PriceLevel(price=Decimal("0.54"), quantity=10),),
            received_ts=datetime.now(UTC),
        )

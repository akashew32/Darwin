from datetime import UTC, datetime
from decimal import Decimal

import pytest

from darwin.domain.enums import BookSide, Exchange, OutcomeSide
from darwin.domain.orderbook import OrderBookDelta, OrderBookSnapshot, PriceLevel
from darwin.exchanges.kalshi.orderbook import LocalOrderBook


@pytest.mark.parametrize("delta,expected", [(5, 15), (-3, 7), (-10, 0)])
def test_orderbook_delta_nonnegative_depth(delta: int, expected: int) -> None:
    book = LocalOrderBook()
    book.apply_snapshot(
        OrderBookSnapshot(
            exchange=Exchange.KALSHI,
            market_id="M",
            bids=(PriceLevel(price=Decimal("0.40"), quantity=10),),
            asks=(PriceLevel(price=Decimal("0.60"), quantity=10),),
            sequence=1,
            received_ts=datetime.now(UTC),
        )
    )
    updated = book.apply_delta(
        OrderBookDelta(
            exchange=Exchange.KALSHI,
            market_id="M",
            side=BookSide.BID,
            outcome=OutcomeSide.YES,
            price=Decimal("0.40"),
            delta_quantity=delta,
            sequence=2,
            received_ts=datetime.now(UTC),
        )
    )
    actual = updated.bids[0].quantity if updated.bids else 0
    assert actual == expected


def test_orderbook_delta_before_snapshot_fails() -> None:
    with pytest.raises(ValueError):
        LocalOrderBook().apply_delta(
            OrderBookDelta(
                exchange=Exchange.KALSHI,
                market_id="M",
                side=BookSide.BID,
                outcome=OutcomeSide.YES,
                price=Decimal("0.40"),
                delta_quantity=1,
                received_ts=datetime.now(UTC),
            )
        )

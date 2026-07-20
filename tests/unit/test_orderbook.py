from datetime import UTC, datetime
from decimal import Decimal

from darwin.domain.enums import Exchange
from darwin.domain.orderbook import OrderBookDelta, OrderBookSnapshot, PriceLevel
from darwin.exchanges.kalshi.mapper import map_orderbook
from darwin.exchanges.kalshi.orderbook import LocalOrderBook


def test_kalshi_book_maps_no_bids_to_yes_asks() -> None:
    snapshot = map_orderbook(
        "M",
        {"orderbook": {"yes": [[40, 10]], "no": [[55, 7]]}, "seq": 1},
        datetime.now(UTC),
    )
    assert snapshot.best_bid == Decimal("0.4")
    assert snapshot.best_ask == Decimal("0.45")


def test_apply_delta_updates_depth() -> None:
    book = LocalOrderBook()
    book.apply_snapshot(
        OrderBookSnapshot(
            exchange=Exchange.KALSHI,
            market_id="M",
            bids=(PriceLevel(price=Decimal("0.4"), quantity=10),),
            asks=(PriceLevel(price=Decimal("0.5"), quantity=10),),
            sequence=1,
            received_ts=datetime.now(UTC),
        )
    )
    updated = book.apply_delta(
        OrderBookDelta(
            exchange=Exchange.KALSHI,
            market_id="M",
            side="bid",
            outcome="yes",
            price=Decimal("0.4"),
            delta_quantity=5,
            sequence=2,
            received_ts=datetime.now(UTC),
        )
    )
    assert updated.bids[0].quantity == 15

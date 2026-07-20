from datetime import UTC, datetime
from decimal import Decimal

from darwin.exchanges.kalshi.mapper import map_delta, map_orderbook


def test_orderbook_fp_mapping() -> None:
    snapshot = map_orderbook(
        "M",
        {
            "orderbook_fp": {
                "yes_dollars": [["0.4000", "10.00"]],
                "no_dollars": [["0.5500", "7.00"]],
            }
        },
        datetime.now(UTC),
    )
    assert snapshot.best_bid == Decimal("0.4000")
    assert snapshot.best_ask == Decimal("0.4500")


def test_delta_fp_mapping() -> None:
    delta = map_delta(
        {
            "seq": 4,
            "msg": {
                "market_ticker": "M",
                "price_dollars": "0.4000",
                "delta_fp": "-2.00",
                "side": "yes",
            },
        },
        datetime.now(UTC),
    )
    assert delta.delta_quantity == -2
    assert delta.price == Decimal("0.4000")

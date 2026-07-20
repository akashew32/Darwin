from datetime import UTC, datetime, timedelta
from decimal import Decimal

from darwin.domain.enums import Exchange
from darwin.domain.orderbook import OrderBookSnapshot, PriceLevel
from darwin.features.pipeline import StatefulFeaturePipeline


def snap(price: str, seconds: int) -> OrderBookSnapshot:
    mid = Decimal(price)
    return OrderBookSnapshot(
        exchange=Exchange.KALSHI,
        market_id="M",
        bids=(PriceLevel(price=mid - Decimal("0.01"), quantity=10),),
        asks=(PriceLevel(price=mid + Decimal("0.01"), quantity=10),),
        received_ts=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds),
    )


def test_future_events_do_not_mutate_prior_feature_vector() -> None:
    pipeline = StatefulFeaturePipeline()
    first = pipeline.update(snap("0.50", 0))
    first_values = dict(first.values)
    pipeline.update(snap("0.60", 1))
    assert first.values == first_values

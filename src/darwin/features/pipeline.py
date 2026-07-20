from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal

from darwin.domain.orderbook import OrderBookSnapshot
from darwin.domain.signal import FeatureVector
from darwin.features.microstructure import depth_imbalance, microprice, spread


@dataclass(frozen=True)
class FeaturePipeline:
    def from_snapshot(self, snapshot: OrderBookSnapshot) -> FeatureVector:
        mid = snapshot.midprice
        mp = microprice(snapshot)
        return FeatureVector(
            market_id=snapshot.market_id,
            asof_ts=snapshot.received_ts,
            values={
                "best_bid": float(snapshot.best_bid or 0),
                "best_ask": float(snapshot.best_ask or 0),
                "midprice": float(mid or 0),
                "microprice": float(mp or mid or 0),
                "spread": spread(snapshot) or 1.0,
                "depth_imbalance_3": depth_imbalance(snapshot, 3),
                "top_depth": float(
                    sum(level.quantity for level in snapshot.bids[:1])
                    + sum(level.quantity for level in snapshot.asks[:1])
                ),
                "data_age_seconds": 0.0,
            },
        )


@dataclass
class StatefulFeaturePipeline:
    history_size: int = 20
    mid_history: dict[str, deque[Decimal]] = field(default_factory=dict)

    def update(self, snapshot: OrderBookSnapshot) -> FeatureVector:
        base = FeaturePipeline().from_snapshot(snapshot)
        history = self.mid_history.setdefault(snapshot.market_id, deque(maxlen=self.history_size))
        mid = snapshot.midprice or Decimal("0")
        previous = history[-1] if history else mid
        history.append(mid)
        values = dict(base.values)
        values["momentum"] = float(mid - previous)
        values["return_1"] = float((mid - previous) / previous) if previous else 0.0
        values["realized_volatility"] = _realized_volatility(list(history))
        values["distance_from_0_5"] = float(abs(mid - Decimal("0.5")))
        values["depth_imbalance_1"] = depth_imbalance(snapshot, 1)
        values["depth_imbalance_5"] = depth_imbalance(snapshot, 5)
        values["depth_imbalance_10"] = depth_imbalance(snapshot, 10)
        return FeatureVector(market_id=snapshot.market_id, asof_ts=snapshot.received_ts, values=values)


def _realized_volatility(values: list[Decimal]) -> float:
    if len(values) < 2:
        return 0.0
    returns = [float(values[i] - values[i - 1]) for i in range(1, len(values))]
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / len(returns)
    return variance**0.5

from dataclasses import dataclass

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
            },
        )

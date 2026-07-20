from dataclasses import dataclass
from decimal import Decimal

from darwin.config import StrategyConfig
from darwin.domain.enums import Exchange, OrderIntent, OutcomeSide
from darwin.domain.order import OrderRequest
from darwin.domain.signal import FeatureVector, Signal
from darwin.strategies.base import Strategy


@dataclass
class MomentumStrategy(Strategy):
    config: StrategyConfig

    def generate(self, features: FeatureVector) -> Signal:
        values = features.values
        spread = values.get("spread", 1.0)
        depth = values.get("top_depth", 0.0)
        imbalance = values.get("depth_imbalance_3", 0.0)
        momentum = values.get("return_ewm", values.get("momentum", 0.0))
        flow = values.get("trade_flow_imbalance", 0.0)
        breakout = values.get("breakout_strength", 0.0)
        volatility = max(0.0, values.get("realized_volatility", 0.0) - 0.02)
        staleness = max(0.0, values.get("data_age_seconds", 0.0) / 10)
        w = self.config.weights
        score = (
            w["momentum"] * momentum
            + w["book"] * imbalance
            + w["flow"] * flow
            + w["breakout"] * breakout
            - w["spread"] * spread
            - w["volatility"] * volatility
            - w["staleness"] * staleness
        )
        reasons: list[str] = []
        action = "hold"
        outcome: OutcomeSide | None = None
        order: OrderRequest | None = None
        edge = Decimal(str(score)).quantize(Decimal("0.0001"))
        mid = Decimal(str(values.get("midprice", 0.5)))
        if spread > self.config.max_spread:
            reasons.append("spread_too_wide")
        if depth < self.config.min_depth:
            reasons.append("insufficient_depth")
        if mid < Decimal(str(self.config.no_trade_extreme_probability)) or mid > Decimal(
            str(1 - self.config.no_trade_extreme_probability)
        ):
            reasons.append("extreme_probability_no_trade")
        if not reasons and score >= self.config.entry_threshold:
            action = "enter"
            outcome = OutcomeSide.YES
            order = OrderRequest(
                exchange=Exchange.KALSHI,
                market_id=features.market_id,
                outcome=OutcomeSide.YES,
                intent=OrderIntent.BUY,
                limit_price=mid,
                quantity=self.config.order_quantity,
                client_order_id=f"darwin-{features.market_id}-{int(features.asof_ts.timestamp())}",
                created_ts=features.asof_ts,
            )
            reasons.append("positive_momentum_with_book_confirmation")
        elif not reasons and score <= -self.config.entry_threshold:
            action = "enter"
            outcome = OutcomeSide.NO
            order = OrderRequest(
                exchange=Exchange.KALSHI,
                market_id=features.market_id,
                outcome=OutcomeSide.NO,
                intent=OrderIntent.BUY,
                limit_price=Decimal("1") - mid,
                quantity=self.config.order_quantity,
                client_order_id=f"darwin-{features.market_id}-{int(features.asof_ts.timestamp())}",
                created_ts=features.asof_ts,
            )
            reasons.append("negative_momentum_with_book_confirmation")
        return Signal(
            market_id=features.market_id,
            asof_ts=features.asof_ts,
            outcome=outcome,
            score=score,
            expected_edge=edge,
            action=action,
            reasons=tuple(reasons or ["below_entry_threshold"]),
            order=order,
        )

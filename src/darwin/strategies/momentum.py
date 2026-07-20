from dataclasses import dataclass, field
from decimal import Decimal

from darwin.config import StrategyConfig
from darwin.domain.enums import Exchange, OrderIntent, OutcomeSide
from darwin.domain.order import OrderRequest
from darwin.domain.signal import FeatureVector, StrategyDecision
from darwin.execution.client_order_id import ClientOrderIdFactory
from darwin.execution.fees import kalshi_fee_estimate
from darwin.strategies.base import Strategy, StrategyContext


@dataclass
class MomentumStrategy(Strategy):
    config: StrategyConfig
    strategy_id: str = "momentum"
    id_factory: ClientOrderIdFactory = field(init=False)

    def __post_init__(self) -> None:
        self.id_factory = ClientOrderIdFactory(self.strategy_id)

    def decide(self, features: FeatureVector, context: StrategyContext) -> StrategyDecision:
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

        mid = Decimal(str(values.get("midprice", 0.5))).quantize(Decimal("0.0001"))
        best_bid = Decimal(str(values.get("best_bid", mid))).quantize(Decimal("0.0001"))
        best_ask = Decimal(str(values.get("best_ask", mid))).quantize(Decimal("0.0001"))
        fair = min(Decimal("0.99"), max(Decimal("0.01"), mid + Decimal(str(score)) / Decimal("10")))
        reasons: list[str] = []
        proposed: list[OrderRequest] = []
        action = "hold"
        target = 0

        position = context.position
        yes_qty = 0 if position is None else position.yes_quantity
        no_qty = 0 if position is None else position.no_quantity
        net_yes = yes_qty - no_qty
        has_open_equivalent = any(
            o.request.market_id == features.market_id for o in context.open_orders
        )

        if spread > self.config.max_spread:
            reasons.append("spread_too_wide")
        if depth < self.config.min_depth:
            reasons.append("insufficient_depth")
        if values.get("data_age_seconds", 0.0) > 5:
            reasons.append("stale_data")
        if mid < Decimal(str(self.config.no_trade_extreme_probability)) or mid > Decimal(
            str(1 - self.config.no_trade_extreme_probability)
        ):
            reasons.append("extreme_probability_no_trade")

        stop_loss = context.unrealized_pnl <= Decimal("-0.50") and net_yes != 0
        take_profit = context.unrealized_pnl >= Decimal("0.50") and net_yes != 0
        reversal_exit = net_yes > 0 and score < -self.config.exit_threshold
        no_reversal_exit = net_yes < 0 and score > self.config.exit_threshold
        if stop_loss or take_profit or reversal_exit or no_reversal_exit:
            action = "exit"
            target = 0
            reasons.append(
                "stop_loss" if stop_loss else "take_profit" if take_profit else "momentum_reversal"
            )
            outcome = OutcomeSide.YES if net_yes > 0 else OutcomeSide.NO
            price = best_bid if outcome == OutcomeSide.YES else Decimal("1") - best_ask
            proposed.append(
                self._order(features, outcome, OrderIntent.SELL, price, abs(net_yes), "exit")
            )
        elif (
            not reasons
            and not has_open_equivalent
            and net_yes == 0
            and score >= self.config.entry_threshold
        ):
            action = "enter"
            target = self.config.order_quantity
            reasons.append("positive_momentum_with_book_confirmation")
            proposed.append(
                self._order(
                    features,
                    OutcomeSide.YES,
                    OrderIntent.BUY,
                    best_ask,
                    self.config.order_quantity,
                    "enter_yes",
                )
            )
        elif (
            not reasons
            and not has_open_equivalent
            and net_yes == 0
            and score <= -self.config.entry_threshold
        ):
            action = "enter"
            target = -self.config.order_quantity
            reasons.append("negative_momentum_with_book_confirmation")
            proposed.append(
                self._order(
                    features,
                    OutcomeSide.NO,
                    OrderIntent.BUY,
                    Decimal("1") - best_bid,
                    self.config.order_quantity,
                    "enter_no",
                )
            )
        elif has_open_equivalent:
            reasons.append("equivalent_order_open")

        executable = proposed[0].limit_price if proposed else mid
        fees = kalshi_fee_estimate(executable, proposed[0].quantity) if proposed else Decimal("0")
        slippage = Decimal(str(spread)) / Decimal("2")
        gross_edge = abs(fair - executable)
        net_edge = gross_edge - fees - slippage - Decimal("0.0025")

        return StrategyDecision(
            market_id=features.market_id,
            asof_ts=features.asof_ts,
            action=action,
            target_yes_position=target,
            score=score,
            estimated_fair_value=fair,
            estimated_executable_price=executable,
            gross_edge=gross_edge,
            estimated_fees=fees,
            estimated_slippage=slippage,
            net_edge=net_edge,
            reasons=tuple(reasons or ["below_entry_threshold"]),
            proposed_orders=tuple(proposed),
        )

    def _order(
        self,
        features: FeatureVector,
        outcome: OutcomeSide,
        intent: OrderIntent,
        price: Decimal,
        quantity: int,
        action: str,
    ) -> OrderRequest:
        return OrderRequest(
            exchange=Exchange.KALSHI,
            market_id=features.market_id,
            outcome=outcome,
            intent=intent,
            limit_price=price,
            quantity=quantity,
            client_order_id=self.id_factory.next(features.market_id, features.asof_ts, action),
            created_ts=features.asof_ts,
        )

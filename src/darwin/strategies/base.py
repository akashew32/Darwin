from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from darwin.domain.market import Market
from darwin.domain.order import Order
from darwin.domain.position import Position
from darwin.domain.signal import FeatureVector, Signal, StrategyDecision


@dataclass(frozen=True)
class StrategyContext:
    market: Market | None
    position: Position | None
    open_orders: tuple[Order, ...]
    time_since_entry_seconds: float | None = None
    unrealized_pnl: Decimal = Decimal("0")
    recent_decisions: tuple[StrategyDecision, ...] = ()
    now: datetime | None = None


class Strategy(ABC):
    @abstractmethod
    def decide(self, features: FeatureVector, context: StrategyContext) -> StrategyDecision: ...

    def generate(self, features: FeatureVector) -> Signal:
        decision = self.decide(
            features,
            StrategyContext(market=None, position=None, open_orders=(), now=features.asof_ts),
        )
        return Signal(
            market_id=decision.market_id,
            asof_ts=decision.asof_ts,
            outcome=decision.proposed_orders[0].outcome if decision.proposed_orders else None,
            score=decision.score,
            expected_edge=decision.net_edge,
            action=decision.action,
            reasons=decision.reasons,
            order=decision.proposed_orders[0] if decision.proposed_orders else None,
        )

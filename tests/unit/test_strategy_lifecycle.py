from datetime import UTC, datetime
from decimal import Decimal

import pytest

from darwin.config import StrategyConfig
from darwin.domain.position import Position
from darwin.domain.signal import FeatureVector
from darwin.strategies.base import StrategyContext
from darwin.strategies.momentum import MomentumStrategy


def features(momentum: float, spread: float = 0.02, depth: float = 100) -> FeatureVector:
    return FeatureVector(
        market_id="M",
        asof_ts=datetime.now(UTC),
        values={
            "midprice": 0.50,
            "best_bid": 0.49,
            "best_ask": 0.51,
            "spread": spread,
            "top_depth": depth,
            "depth_imbalance_3": 0.5,
            "momentum": momentum,
        },
    )


@pytest.mark.parametrize("momentum,action", [(2.0, "enter"), (-2.0, "enter"), (0.0, "hold")])
def test_strategy_entry_and_hold(momentum: float, action: str) -> None:
    decision = MomentumStrategy(StrategyConfig(entry_threshold=0.5, min_depth=1)).decide(
        features(momentum), StrategyContext(market=None, position=None, open_orders=())
    )
    assert decision.action == action


@pytest.mark.parametrize(
    "unrealized,momentum,reason",
    [
        (Decimal("-1"), 0.0, "stop_loss"),
        (Decimal("1"), 0.0, "take_profit"),
        (Decimal("0"), -2.0, "momentum_reversal"),
    ],
)
def test_strategy_exits(unrealized: Decimal, momentum: float, reason: str) -> None:
    position = Position(market_id="M", yes_quantity=3, average_yes_cost=Decimal("0.40"))
    decision = MomentumStrategy(
        StrategyConfig(entry_threshold=0.5, exit_threshold=0.2, min_depth=1)
    ).decide(
        features(momentum),
        StrategyContext(market=None, position=position, open_orders=(), unrealized_pnl=unrealized),
    )
    assert decision.action == "exit"
    assert reason in decision.reasons


def test_strategy_avoids_duplicate_open_order() -> None:
    strategy = MomentumStrategy(StrategyConfig(entry_threshold=0.5, min_depth=1))
    first = strategy.decide(
        features(2.0), StrategyContext(market=None, position=None, open_orders=())
    )
    assert first.proposed_orders
    open_order = __import__("darwin.domain.order", fromlist=["Order"]).Order.created(
        first.proposed_orders[0]
    )
    second = strategy.decide(
        features(2.0), StrategyContext(market=None, position=None, open_orders=(open_order,))
    )
    assert second.action == "hold"
    assert "equivalent_order_open" in second.reasons

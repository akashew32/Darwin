from datetime import UTC, datetime
from decimal import Decimal

from darwin.config import RiskConfig, StrategyConfig
from darwin.domain.enums import Exchange
from darwin.domain.orderbook import OrderBookSnapshot, PriceLevel
from darwin.domain.portfolio import PortfolioState
from darwin.features.pipeline import FeaturePipeline
from darwin.risk.engine import RiskEngine
from darwin.risk.kill_switch import KillSwitch
from darwin.strategies.momentum import MomentumStrategy


def test_strategy_generates_explainable_signal(tmp_path) -> None:
    snapshot = OrderBookSnapshot(
        exchange=Exchange.KALSHI,
        market_id="M",
        bids=(PriceLevel(price=Decimal("0.50"), quantity=100),),
        asks=(PriceLevel(price=Decimal("0.52"), quantity=20),),
        received_ts=datetime.now(UTC),
    )
    features = FeaturePipeline().from_snapshot(snapshot)
    features = features.model_copy(update={"values": features.values | {"momentum": 2.0}})
    signal = MomentumStrategy(StrategyConfig(entry_threshold=0.5)).generate(features)
    assert signal.action == "enter"
    assert signal.order is not None
    risk = RiskEngine(
        RiskConfig(min_available_cash=0, min_expected_edge=-1), KillSwitch(tmp_path / "kill.json")
    )
    decision = risk.check(
        signal.order,
        PortfolioState(cash=Decimal("1000")),
        spread=0.02,
        data_age_seconds=0,
        expected_edge=signal.expected_edge,
        asof_ts=signal.asof_ts,
    )
    assert decision.decision.value == "approved"


def test_kill_switch_rejects_order(tmp_path) -> None:
    kill = KillSwitch(tmp_path / "kill.json")
    kill.activate("test")
    snapshot = OrderBookSnapshot(
        exchange=Exchange.KALSHI,
        market_id="M",
        bids=(PriceLevel(price=Decimal("0.50"), quantity=100),),
        asks=(PriceLevel(price=Decimal("0.52"), quantity=20),),
        received_ts=datetime.now(UTC),
    )
    features = FeaturePipeline().from_snapshot(snapshot)
    features = features.model_copy(update={"values": features.values | {"momentum": 2.0}})
    signal = MomentumStrategy(StrategyConfig(entry_threshold=0.5)).generate(features)
    assert signal.order is not None
    decision = RiskEngine(RiskConfig(min_available_cash=0, min_expected_edge=-1), kill).check(
        signal.order,
        PortfolioState(cash=Decimal("1000")),
        spread=0.02,
        data_age_seconds=0,
        expected_edge=signal.expected_edge,
        asof_ts=signal.asof_ts,
    )
    assert "kill_switch_active" in decision.reasons

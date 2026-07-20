from decimal import Decimal

import pytest

from darwin.config import RiskConfig, StrategyConfig
from darwin.execution.config import ExecutionSimulationConfig


@pytest.mark.parametrize("seed", [0, 1, 42, 999])
def test_execution_config_seed_is_stored(seed: int) -> None:
    assert ExecutionSimulationConfig(random_seed=seed).random_seed == seed


@pytest.mark.parametrize("bps", [0, 5, 25])
def test_execution_config_slippage_bps(bps: int) -> None:
    assert ExecutionSimulationConfig(slippage_bps=bps).slippage_bps == bps


def test_risk_config_has_configurable_thresholds() -> None:
    config = RiskConfig(max_estimated_slippage=0.03, daily_loss_limit=10)
    assert config.max_estimated_slippage == 0.03
    assert config.daily_loss_limit == 10


def test_strategy_config_has_configurable_exits() -> None:
    config = StrategyConfig(stop_loss=0.2, take_profit=0.3)
    assert config.stop_loss == 0.2
    assert config.take_profit == 0.3


def test_max_participation_decimal() -> None:
    assert ExecutionSimulationConfig(
        max_book_participation=Decimal("0.25")
    ).max_book_participation == Decimal("0.25")

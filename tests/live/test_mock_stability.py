import asyncio
from pathlib import Path

import pytest

from darwin.config import RiskConfig, StrategyConfig
from darwin.exchanges.mock import MockMarketDataProvider
from darwin.execution.config import ExecutionSimulationConfig
from darwin.services.live_paper_trader import LivePaperSessionConfig, LivePaperTrader


@pytest.mark.parametrize("minutes", [1, 5, 30])
def test_mock_live_stability_windows_are_bounded(tmp_path: Path, minutes: int) -> None:
    output = tmp_path / f"stability-{minutes}"
    result = asyncio.run(
        LivePaperTrader(
            provider=MockMarketDataProvider(),
            strategy_config=StrategyConfig(order_quantity=5, max_spread=0.5),
            risk_config=RiskConfig(kill_switch_path=tmp_path / f"kill-{minutes}.json"),
            execution_config=ExecutionSimulationConfig(random_seed=42),
            session_config=LivePaperSessionConfig(
                markets=["KXTEST-A", "KXTEST-B"],
                duration_seconds=minutes * 60,
                output=output,
                database_url=f"sqlite:///{tmp_path / f'paper-{minutes}.sqlite3'}",
                seed=42,
                max_events=8,
            ),
        ).run()
    )
    assert result["summary"]["health_halted_reason"] is None
    assert result["summary"]["execution_endpoint_calls"] == 0
    assert len(result["events"]) <= 8
    assert result["summary"]["fills"] == len({row["fill_id"] for row in result["fills"]})

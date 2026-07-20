import asyncio
import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from darwin.cli import app
from darwin.config import RiskConfig, StrategyConfig
from darwin.exchanges.mock import MockMarketDataProvider
from darwin.execution.config import ExecutionSimulationConfig
from darwin.services.live_paper_trader import LivePaperSessionConfig, LivePaperTrader

runner = CliRunner()


@pytest.mark.parametrize("seed", [1, 42, 99])
def test_live_paper_service_mock_smoke(tmp_path: Path, seed: int) -> None:
    output = tmp_path / f"paper-{seed}"
    result = asyncio.run(
        LivePaperTrader(
            provider=MockMarketDataProvider(),
            strategy_config=StrategyConfig(order_quantity=5, max_spread=0.5),
            risk_config=RiskConfig(kill_switch_path=tmp_path / "kill.json"),
            execution_config=ExecutionSimulationConfig(random_seed=seed),
            session_config=LivePaperSessionConfig(
                markets=["KXTEST-A", "KXTEST-B"],
                duration_seconds=10,
                output=output,
                database_url=f"sqlite:///{tmp_path / f'paper-{seed}.sqlite3'}",
                seed=seed,
            ),
        ).run()
    )
    summary = result["summary"]
    assert summary["execution_endpoint_calls"] == 0
    assert summary["orders"] >= 1
    assert summary["fills"] >= 1
    assert summary["risk_rejections"] >= 1
    assert (output / "summary.json").exists()
    assert "sequence_gap" in (output / "health.csv").read_text()


def test_paper_live_cli_mock_smoke(tmp_path: Path) -> None:
    output = tmp_path / "cli"
    result = runner.invoke(
        app,
        [
            "paper-live",
            "--markets",
            "KXTEST-A,KXTEST-B",
            "--duration",
            "10",
            "--exchange-environment",
            "mock",
            "--database-url",
            f"sqlite:///{tmp_path / 'paper.sqlite3'}",
            "--output",
            str(output),
            "--seed",
            "42",
        ],
    )
    assert result.exit_code == 0, result.output
    summary = json.loads((output / "summary.json").read_text())
    assert summary["execution_endpoint_calls"] == 0


def test_paper_live_persists_events(tmp_path: Path) -> None:
    db = tmp_path / "paper.sqlite3"
    output = tmp_path / "persist"
    asyncio.run(
        LivePaperTrader(
            provider=MockMarketDataProvider(),
            strategy_config=StrategyConfig(order_quantity=5, max_spread=0.5),
            risk_config=RiskConfig(kill_switch_path=tmp_path / "kill.json"),
            execution_config=ExecutionSimulationConfig(),
            session_config=LivePaperSessionConfig(
                markets=["KXTEST-A", "KXTEST-B"],
                duration_seconds=10,
                output=output,
                database_url=f"sqlite:///{db}",
                seed=42,
            ),
        ).run()
    )
    with sqlite3.connect(db) as conn:
        count = conn.execute("select count(*) from normalized_events").fetchone()[0]
    assert count >= 5


@pytest.mark.asyncio
async def test_mock_provider_is_read_only() -> None:
    provider = MockMarketDataProvider()
    with pytest.raises(AssertionError):
        await provider.forbidden_submit_order()
    assert provider.execution_endpoint_calls == 1


@pytest.mark.parametrize("market", ["KXTEST-A", "KXTEST-B"])
def test_mock_provider_has_initial_snapshots(market: str) -> None:
    snapshot = asyncio.run(MockMarketDataProvider().get_orderbook(market))
    assert snapshot.bids
    assert snapshot.asks

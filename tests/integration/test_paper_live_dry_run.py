import asyncio
import json
from pathlib import Path

from typer.testing import CliRunner

from darwin.cli import app
from darwin.config import RiskConfig, StrategyConfig
from darwin.exchanges.mock import MockMarketDataProvider
from darwin.execution.config import ExecutionSimulationConfig
from darwin.services.live_paper_trader import LivePaperSessionConfig, LivePaperTrader

runner = CliRunner()


def test_live_paper_dry_run_skips_strategy_orders_and_fills(tmp_path: Path) -> None:
    output = tmp_path / "dry-run"
    result = asyncio.run(
        LivePaperTrader(
            provider=MockMarketDataProvider(),
            strategy_config=StrategyConfig(order_quantity=5, max_spread=0.5),
            risk_config=RiskConfig(kill_switch_path=tmp_path / "kill.json"),
            execution_config=ExecutionSimulationConfig(),
            session_config=LivePaperSessionConfig(
                markets=["KXTEST-A", "KXTEST-B"],
                duration_seconds=10,
                output=output,
                database_url=f"sqlite:///{tmp_path / 'dry.sqlite3'}",
                seed=42,
                dry_run=True,
            ),
        ).run()
    )
    assert result["summary"]["dry_run"] is True
    assert result["summary"]["orders"] == 0
    assert result["summary"]["fills"] == 0
    assert (output / "books.csv").read_text()


def test_live_paper_dry_run_writes_validation_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "dry-artifacts"
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
                database_url=f"sqlite:///{tmp_path / 'dry-artifacts.sqlite3'}",
                seed=42,
                dry_run=True,
            ),
        ).run()
    )
    expected = {
        "connection_summary.json",
        "subscriptions.json",
        "market_health.csv",
        "sequence_events.csv",
        "received_message_types.csv",
        "orderbook_validation.csv",
        "metrics.prom",
        "dry_run_report.html",
    }
    assert expected.issubset({path.name for path in output.iterdir()})


def test_live_paper_dry_run_metrics_are_prometheus_style(tmp_path: Path) -> None:
    output = tmp_path / "dry-metrics"
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
                database_url=f"sqlite:///{tmp_path / 'dry-metrics.sqlite3'}",
                seed=42,
                dry_run=True,
            ),
        ).run()
    )
    metrics = (output / "metrics.prom").read_text()
    assert "darwin_paper_execution_endpoint_calls_total 0" in metrics


def test_paper_live_cli_dry_run_mock(tmp_path: Path) -> None:
    output = tmp_path / "dry-cli"
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
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    summary = json.loads((output / "summary.json").read_text())
    assert summary["dry_run"] is True
    assert summary["orders"] == 0


def test_paper_live_cli_kalshi_requires_read_only_ws_credentials(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "paper-live",
            "--markets",
            "KXTEST-A",
            "--exchange-environment",
            "kalshi",
            "--database-url",
            f"sqlite:///{tmp_path / 'paper.sqlite3'}",
            "--output",
            str(tmp_path / "out"),
            "--dry-run",
        ],
    )
    assert result.exit_code != 0
    assert "WebSocket market data requires" in result.output

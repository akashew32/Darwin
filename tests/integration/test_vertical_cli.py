import json
from pathlib import Path

from typer.testing import CliRunner

from darwin.cli import app


runner = CliRunner()


def test_backtest_cli_outputs_reports(tmp_path: Path) -> None:
    output = tmp_path / "backtest"
    result = runner.invoke(
        app,
        [
            "backtest",
            "--input",
            "tests/replay/multi_market_session.jsonl",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    summary = json.loads((output / "summary.json").read_text())
    assert summary["fill_count"] >= 1
    assert (output / "report.html").exists()


def test_walk_forward_cli_outputs_reports(tmp_path: Path) -> None:
    output = tmp_path / "wf"
    result = runner.invoke(
        app,
        ["walk-forward", "--input", "tests/replay/multi_market_session.jsonl", "--output", str(output)],
    )
    assert result.exit_code == 0, result.output
    assert json.loads((output / "summary.json").read_text())["fold_count"] == 1


def test_paper_cli_never_submits_live_orders(tmp_path: Path) -> None:
    output = tmp_path / "paper"
    result = runner.invoke(
        app,
        [
            "paper",
            "--markets",
            "KXTEST-YES,KXTEST-REJECT",
            "--input",
            "tests/replay/multi_market_session.jsonl",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "submitted_live_orders" in (output / "paper_session.json").read_text()

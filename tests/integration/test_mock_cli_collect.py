import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from darwin.cli import app

runner = CliRunner()


def test_markets_sync_mock_writes_metadata(tmp_path: Path) -> None:
    output = tmp_path / "markets.json"
    result = runner.invoke(
        app, ["markets", "sync", "--environment", "mock", "--output", str(output)]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text())
    assert len(payload["markets"]) == 2


@pytest.mark.parametrize("duration", [1, 3, 5])
def test_collect_mock_writes_events(tmp_path: Path, duration: int) -> None:
    output = tmp_path / "events.jsonl"
    result = runner.invoke(
        app,
        [
            "collect",
            "--markets",
            "KXTEST-A,KXTEST-B",
            "--duration",
            str(duration),
            "--environment",
            "mock",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(output.read_text().splitlines()) == duration


@pytest.mark.parametrize("command", [["markets", "sync"], ["collect", "--markets", "KXTEST-A"]])
def test_non_mock_readonly_commands_fail_actionably(command: list[str]) -> None:
    result = runner.invoke(app, [*command, "--environment", "production"])
    assert result.exit_code != 0

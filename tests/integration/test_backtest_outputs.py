import csv
import json
from decimal import Decimal
from pathlib import Path

from darwin.backtest.engine import BacktestEngine
from darwin.config import RiskConfig, load_strategy_config


def test_backtest_outputs_required_files(tmp_path: Path) -> None:
    output = tmp_path / "sample"
    result = BacktestEngine.from_replay(
        Path("tests/replay/multi_market_session.jsonl"),
        strategy_config=load_strategy_config(Path("config/strategies/momentum.yaml")),
        risk_config=RiskConfig(kill_switch_path=tmp_path / "kill.json"),
        initial_cash=Decimal("10000"),
        output=output,
    )
    for name in [
        "summary.json",
        "trades.csv",
        "orders.csv",
        "fills.csv",
        "signals.csv",
        "equity_curve.csv",
        "positions.csv",
        "risk_decisions.csv",
        "config_snapshot.yaml",
        "report.html",
    ]:
        assert (output / name).exists()
    assert result["summary"]["net_pnl"] != 0
    assert json.loads((output / "summary.json").read_text())["fill_count"] == 2


def test_backtest_has_rejection_and_partial_fill(tmp_path: Path) -> None:
    output = tmp_path / "sample"
    BacktestEngine.from_replay(
        Path("tests/replay/multi_market_session.jsonl"),
        strategy_config=load_strategy_config(Path("config/strategies/momentum.yaml")),
        risk_config=RiskConfig(kill_switch_path=tmp_path / "kill.json"),
        initial_cash=Decimal("10000"),
        output=output,
    )
    risk_rows = list(csv.DictReader((output / "risk_decisions.csv").open()))
    order_rows = list(csv.DictReader((output / "orders.csv").open()))
    assert any(row["decision"] == "rejected" for row in risk_rows)
    assert any(int(row["filled_quantity"]) < int(row["quantity"]) for row in order_rows)

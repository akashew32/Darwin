import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from darwin.backtest.engine import BacktestEngine
from darwin.backtest.events import BacktestEvent, read_events
from darwin.config import RiskConfig, load_strategy_config


@dataclass(frozen=True)
class WalkForwardFold:
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime


def rolling_folds(
    times: list[datetime], train_size: int, test_size: int, step: int
) -> list[WalkForwardFold]:
    ordered = sorted(times)
    folds: list[WalkForwardFold] = []
    start = 0
    while start + train_size + test_size <= len(ordered):
        folds.append(
            WalkForwardFold(
                train_start=ordered[start],
                train_end=ordered[start + train_size - 1],
                test_start=ordered[start + train_size],
                test_end=ordered[start + train_size + test_size - 1],
            )
        )
        start += step
    return folds


def run_walk_forward(
    *,
    input: Path,
    strategy: str,
    config_path: Path,
    output: Path,
    initial_cash: Decimal = Decimal("10000"),
) -> dict[str, Any]:
    if strategy != "momentum":
        raise ValueError("only the momentum strategy is implemented")
    events = read_events(str(input))
    folds = (
        [
            WalkForwardFold(
                train_start=events[0].received_ts,
                train_end=events[0].received_ts,
                test_start=events[0].received_ts,
                test_end=events[-1].received_ts,
            )
        ]
        if events
        else []
    )

    output.mkdir(parents=True, exist_ok=True)
    fold_rows: list[dict[str, Any]] = []
    aggregate_equity: list[dict[str, Any]] = []
    for index, fold in enumerate(folds, start=1):
        test_events = _events_in_fold(events, fold)
        fold_output = output / f"fold_{index:03d}"
        result = BacktestEngine(
            strategy_config=load_strategy_config(config_path),
            risk_config=RiskConfig(kill_switch_path=output / "kill_switch.json"),
            initial_cash=initial_cash,
            output=fold_output,
            seed=42 + index,
        ).run(test_events)
        summary = result["summary"]
        fold_rows.append(
            {
                "fold": index,
                "train_start": fold.train_start.isoformat(),
                "train_end": fold.train_end.isoformat(),
                "test_start": fold.test_start.isoformat(),
                "test_end": fold.test_end.isoformat(),
                "net_pnl": summary["net_pnl"],
                "max_drawdown": summary["max_drawdown"],
                "order_count": summary["order_count"],
                "fill_count": summary["fill_count"],
            }
        )
        aggregate_equity.extend(result["equity_curve"])

    aggregate = {
        "fold_count": len(fold_rows),
        "aggregate_net_pnl": sum(row["net_pnl"] for row in fold_rows),
        "robustness_score": _robustness_score(fold_rows),
    }
    pd.DataFrame(fold_rows).to_csv(output / "fold_metrics.csv", index=False)
    pd.DataFrame(aggregate_equity).to_csv(output / "aggregate_equity_curve.csv", index=False)
    (output / "summary.json").write_text(json.dumps(aggregate, indent=2, sort_keys=True))
    (output / "report.html").write_text(_html(aggregate, fold_rows))
    return aggregate


def _events_in_fold(events: list[BacktestEvent], fold: WalkForwardFold) -> list[BacktestEvent]:
    return [event for event in events if fold.test_start <= event.received_ts <= fold.test_end]


def _robustness_score(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    positive = sum(1 for row in rows if row["net_pnl"] > 0) / len(rows)
    drawdown_penalty = sum(abs(row["max_drawdown"]) for row in rows) / max(1, len(rows))
    turnover_penalty = sum(row["order_count"] for row in rows) * 0.01
    return float(max(0.0, positive - drawdown_penalty * 0.01 - turnover_penalty))


def _html(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    fold_rows = "".join(
        f"<tr><td>{row['fold']}</td><td>{row['net_pnl']}</td><td>{row['max_drawdown']}</td></tr>"
        for row in rows
    )
    return f"""
<!doctype html>
<html><body>
<h1>Darwin Walk-Forward Report</h1>
<pre>{json.dumps(summary, indent=2)}</pre>
<table><tr><th>Fold</th><th>Net P&L</th><th>Max Drawdown</th></tr>{fold_rows}</table>
</body></html>
"""

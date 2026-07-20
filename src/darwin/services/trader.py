from decimal import Decimal
from pathlib import Path
from typing import Any

from darwin.backtest.engine import BacktestEngine
from darwin.backtest.events import read_events
from darwin.config import RiskConfig, StrategyConfig


class TraderService:
    async def run_paper_once(self) -> str:
        return "paper_session_available"


def run_mock_paper_session(
    *,
    input_path: Path,
    output: Path,
    markets: list[str],
    duration_seconds: int,
    seed: int,
) -> dict[str, Any]:
    events = read_events(str(input_path))
    if markets:
        market_set = set(markets)
        events = [event for event in events if event.market_id in market_set]
    if duration_seconds > 0 and events:
        start = events[0].received_ts
        events = [
            event
            for event in events
            if (event.received_ts - start).total_seconds() <= duration_seconds
        ]
    output.mkdir(parents=True, exist_ok=True)
    result = BacktestEngine(
        strategy_config=StrategyConfig(order_quantity=5, max_spread=0.5),
        risk_config=RiskConfig(kill_switch_path=output / "kill_switch.json"),
        initial_cash=Decimal("10000"),
        output=output,
        seed=seed,
    ).run(events)
    (output / "paper_session.json").write_text(
        '{"mode":"paper","submitted_live_orders":false,"source":"mock_replay"}\n'
    )
    return result

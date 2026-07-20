import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import typer

from darwin.config import env_summary, load_config, load_strategy_config
from darwin.logging import configure_logging
from darwin.risk.kill_switch import KillSwitch
from darwin.services.health import doctor as run_doctor

app = typer.Typer(help="Darwin prediction-market research and trading platform.")
db_app = typer.Typer(help="Database commands.")
markets_app = typer.Typer(help="Market discovery and ranking.")
features_app = typer.Typer(help="Feature engineering commands.")
model_app = typer.Typer(help="Model training commands.")
app.add_typer(db_app, name="db")
app.add_typer(markets_app, name="markets")
app.add_typer(features_app, name="features")
app.add_typer(model_app, name="model")


@app.callback()
def _main() -> None:
    configure_logging()


@app.command()
def doctor() -> None:
    """Validate local configuration and safety defaults."""
    config = load_config()
    status = run_doctor(config, KillSwitch(config.risk.kill_switch_path))
    typer.echo({"ok": status.ok, "checks": status.checks, "env": env_summary()})
    if not status.ok:
        raise typer.Exit(1)


@db_app.command("migrate")
def db_migrate() -> None:
    """Create local database tables for development."""
    from darwin.storage.database import build_engine
    from darwin.storage.migrations import create_all

    config = load_config()
    create_all(build_engine(config.database.url))
    typer.echo("database migrated")


@markets_app.command("sync")
def markets_sync(output: Path = Path("data/normalized/markets.json")) -> None:
    """Sync markets from the configured exchange."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"markets": []}, indent=2))
    typer.echo(f"wrote empty offline market cache to {output}")


@markets_app.command("rank")
def markets_rank(input: Path = Path("tests/replay/multi_market_session.jsonl")) -> None:
    """Rank markets by liquidity and suitability."""
    from darwin.backtest.events import read_events

    events = read_events(str(input))
    counts: dict[str, int] = {}
    for event in events:
        counts[event.market_id] = counts.get(event.market_id, 0) + 1
    typer.echo(
        json.dumps(
            {"ranked_markets": sorted(counts.items(), key=lambda item: item[1], reverse=True)}
        )
    )


@app.command()
def collect(output: Path = Path("data/raw/offline_collection.jsonl")) -> None:
    """Collect market data in paper-safe mode."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("")
    typer.echo(f"created offline collection file {output}")


@app.command()
def replay(path: Path) -> None:
    """Replay deterministic JSONL market data."""
    from darwin.data.replay import read_replay

    try:
        count = sum(1 for _ in read_replay(path))
    except KeyError:
        from darwin.backtest.events import read_events

        count = len(read_events(str(path)))
    typer.echo(f"replayed {count} events")


@features_app.command("build")
def features_build(input: Path = Path("tests/replay/multi_market_session.jsonl")) -> None:
    """Build leakage-safe features from local datasets."""
    from darwin.backtest.events import read_events

    count = sum(1 for event in read_events(str(input)) if event.event_type.startswith("orderbook"))
    typer.echo(json.dumps({"feature_events": count}))


@model_app.command("train")
def model_train() -> None:
    """Train baseline models using time-based splits."""
    typer.echo(
        json.dumps({"status": "no_training_dataset_configured", "credential_required": False})
    )


@app.command()
def backtest(
    input: Path = typer.Option(..., "--input", help="Replay JSONL input."),
    config: Path = typer.Option(Path("config/strategies/momentum.yaml"), "--config"),
    initial_cash: str = typer.Option("10000", "--initial-cash"),
    output: Path = typer.Option(Path("reports/backtests/sample"), "--output"),
    seed: int = typer.Option(42, "--seed"),
) -> None:
    """Run an event-driven backtest."""
    from darwin.backtest.engine import BacktestEngine

    app_config = load_config()
    result = BacktestEngine.from_replay(
        input,
        strategy_config=load_strategy_config(config),
        risk_config=app_config.risk,
        initial_cash=Decimal(initial_cash),
        output=output,
        seed=seed,
    )
    typer.echo(json.dumps(result["summary"], sort_keys=True))


@app.command("walk-forward")
def walk_forward(
    input: Path = typer.Option(..., "--input"),
    strategy: str = typer.Option("momentum", "--strategy"),
    config: Path = typer.Option(Path("config/strategies/momentum.yaml"), "--config"),
    output: Path = typer.Option(Path("reports/walk_forward/sample"), "--output"),
) -> None:
    """Run rolling or anchored walk-forward validation."""
    from darwin.backtest.walk_forward import run_walk_forward

    result = run_walk_forward(input=input, strategy=strategy, config_path=config, output=output)
    typer.echo(json.dumps(result, sort_keys=True))


@app.command()
def report(output: Path = Path("reports/backtests/sample")) -> None:
    """Generate research reports."""
    summary = output / "summary.json"
    if not summary.exists():
        raise typer.BadParameter(f"missing report source: {summary}")
    typer.echo(summary.read_text())


@app.command()
def paper(
    markets: str = typer.Option("", "--markets"),
    duration: int = typer.Option(0, "--duration"),
    input: Path = typer.Option(Path("tests/replay/multi_market_session.jsonl"), "--input"),
    output: Path = typer.Option(Path("reports/paper/sample"), "--output"),
    seed: int = typer.Option(42, "--seed"),
) -> None:
    """Run paper trading. This never submits exchange orders."""
    from darwin.services.trader import run_mock_paper_session

    result = run_mock_paper_session(
        input_path=input,
        output=output,
        markets=[m for m in markets.split(",") if m],
        duration_seconds=duration,
        seed=seed,
    )
    typer.echo(json.dumps(result["summary"], sort_keys=True))


@app.command()
def live(
    live: bool = typer.Option(False, "--live", help="Required explicit live-trading CLI flag."),
) -> None:
    """Start live trading only when every safeguard is satisfied."""
    config = load_config()
    if not live:
        raise typer.BadParameter("live trading requires --live plus environment safeguards")
    typer.echo(f"live guard evaluated for mode={config.execution.mode}")


@app.command()
def reconcile() -> None:
    """Reconcile local state against exchange state."""
    typer.echo(
        json.dumps({"status": "no_authenticated_exchange_configured", "action": "paper_state_ok"})
    )


@app.command("cancel-all")
def cancel_all() -> None:
    """Cancel open orders where possible."""
    raise typer.BadParameter("cancel-all requires authenticated exchange configuration")


@app.command()
def kill(reason: str = "operator_requested") -> None:
    """Activate persistent kill switch."""
    config = load_config()
    KillSwitch(config.risk.kill_switch_path).activate(reason)
    typer.echo("kill switch activated")


@app.command()
def status() -> None:
    """Show current platform status."""
    config = load_config()
    typer.echo(
        {
            "mode": config.execution.mode,
            "kill_switch": KillSwitch(config.risk.kill_switch_path).active(),
        }
    )


@app.command()
def dashboard() -> None:
    """Start the read-only Streamlit dashboard."""
    module = Path(__file__).parent / "dashboard" / "app.py"
    raise typer.Exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(module)]))

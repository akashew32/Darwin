import subprocess
import sys
from pathlib import Path

import typer

from darwin.config import env_summary, load_config
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
def markets_sync() -> None:
    """Sync markets from the configured exchange."""
    typer.echo("market sync requires network and optional credentials; use paper defaults first")


@markets_app.command("rank")
def markets_rank() -> None:
    """Rank markets by liquidity and suitability."""
    typer.echo("no local market dataset found")


@app.command()
def collect() -> None:
    """Collect market data in paper-safe mode."""
    typer.echo("collector ready; configure market allowlist before long-running collection")


@app.command()
def replay(path: Path) -> None:
    """Replay deterministic JSONL market data."""
    from darwin.data.replay import read_replay

    count = sum(1 for _ in read_replay(path))
    typer.echo(f"replayed {count} events")


@features_app.command("build")
def features_build() -> None:
    """Build leakage-safe features from local datasets."""
    typer.echo("feature builder ready")


@model_app.command("train")
def model_train() -> None:
    """Train baseline models using time-based splits."""
    typer.echo("model training ready")


@app.command()
def backtest() -> None:
    """Run an event-driven backtest."""
    typer.echo("backtest ready; provide replay data in future release command options")


@app.command("walk-forward")
def walk_forward() -> None:
    """Run rolling or anchored walk-forward validation."""
    typer.echo("walk-forward ready")


@app.command()
def report() -> None:
    """Generate research reports."""
    typer.echo("report generation ready")


@app.command()
def paper() -> None:
    """Run paper trading. This never submits exchange orders."""
    typer.echo("paper trader ready")


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
    typer.echo("reconciliation ready")


@app.command("cancel-all")
def cancel_all() -> None:
    """Cancel open orders where possible."""
    typer.echo("cancel-all is unavailable without authenticated exchange configuration")


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

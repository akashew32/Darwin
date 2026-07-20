from dataclasses import dataclass

from darwin.config import DarwinConfig
from darwin.domain.enums import TradingMode
from darwin.risk.kill_switch import KillSwitch


@dataclass(frozen=True)
class HealthStatus:
    ok: bool
    checks: dict[str, bool]


def doctor(config: DarwinConfig, kill_switch: KillSwitch) -> HealthStatus:
    checks = {
        "paper_default": config.execution.mode in {TradingMode.PAPER, TradingMode.BACKTEST},
        "database_configured": bool(config.database.url),
        "kill_switch_clear": not kill_switch.active(),
        "live_ack_guard": config.execution.mode != TradingMode.LIVE,
    }
    return HealthStatus(ok=all(checks.values()), checks=checks)

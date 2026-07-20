from darwin.config import DarwinConfig, require_live_cli_flag
from darwin.domain.enums import TradingMode
from darwin.exchanges.base import ExchangeClient
from darwin.risk.kill_switch import KillSwitch


class LiveBroker:
    def __init__(
        self,
        config: DarwinConfig,
        exchange: ExchangeClient,
        kill_switch: KillSwitch,
        *,
        live_flag: bool,
    ) -> None:
        require_live_cli_flag(config, live_flag)
        if config.execution.mode != TradingMode.LIVE:
            raise ValueError("LiveBroker can only be created when TRADING_MODE=live")
        if not config.exchange.has_credentials:
            raise ValueError("live broker requires valid exchange credentials")
        if kill_switch.active():
            raise ValueError("live broker cannot start while kill switch is active")
        self.exchange = exchange

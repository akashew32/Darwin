import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from darwin.domain.enums import TradingMode


class AppConfig(BaseModel):
    env: str = "paper"
    service_name: str = "darwin"
    data_dir: Path = Path("data")


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./darwin.sqlite3"


class ExchangeConfig(BaseModel):
    name: Literal["kalshi"] = "kalshi"
    environment: Literal["demo", "production"] = "demo"
    api_key_id: SecretStr | None = None
    private_key_path: Path | None = None
    private_key: SecretStr | None = None
    request_timeout_seconds: float = 10

    @property
    def rest_base_url(self) -> str:
        if self.environment == "production":
            return "https://external-api.kalshi.com"
        return "https://external-api.demo.kalshi.co"

    @property
    def websocket_url(self) -> str:
        if self.environment == "production":
            return "wss://external-api-ws.kalshi.com/trade-api/ws/v2"
        return "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2"

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key_id and (self.private_key_path or self.private_key))


class RiskConfig(BaseModel):
    max_order_size: int = 10
    max_position_per_market: int = 50
    max_gross_contracts: int = 200
    max_open_orders: int = 20
    max_spread: float = 0.08
    max_market_data_age_seconds: float = 5
    min_available_cash: float = 100.0
    min_expected_edge: float = 0.01
    near_close_minutes: int = 15
    kill_switch_path: Path = Path("data/kill_switch.json")
    max_estimated_slippage: float = 0.05
    daily_loss_limit: float = 100.0
    max_drawdown: float = 250.0
    exchange_error_limit: int = 3
    rejection_limit: int = 5
    max_queue_utilization: float = 0.9
    max_reconnect_count: int = 5
    max_sequence_gaps: int = 3
    max_clock_drift_seconds: float = 2.0
    max_depth_participation: float = 0.5


class ExecutionConfig(BaseModel):
    mode: TradingMode = TradingMode.PAPER
    live_acknowledgement: str | None = None
    startup_delay_seconds: int = 15

    @model_validator(mode="after")
    def _live_guard(self) -> "ExecutionConfig":
        if self.mode == TradingMode.LIVE and self.live_acknowledgement != "I_UNDERSTAND_LIVE_RISK":
            raise ValueError("live mode requires DARWIN_LIVE_TRADING_ACK=I_UNDERSTAND_LIVE_RISK")
        return self


class StrategyConfig(BaseModel):
    entry_threshold: float = 0.65
    exit_threshold: float = 0.25
    hysteresis: float = 0.05
    min_depth: int = 20
    max_spread: float = 0.08
    order_quantity: int = 1
    max_order_age_seconds: int = 30
    no_trade_extreme_probability: float = 0.03
    stop_loss: float = 0.50
    take_profit: float = 0.50
    entry_cooldown_seconds: int = 0
    reentry_cooldown_seconds: int = 0
    minimum_holding_seconds: int = 0
    maximum_holding_seconds: int = 3600
    trailing_stop: float | None = None
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "momentum": 0.45,
            "book": 0.25,
            "flow": 0.15,
            "breakout": 0.10,
            "spread": 0.20,
            "volatility": 0.10,
            "staleness": 0.20,
        }
    )


class DarwinConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)


class EnvironmentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    darwin_env: str = "paper"
    trading_mode: TradingMode = TradingMode.PAPER
    database_url: str = "sqlite:///./darwin.sqlite3"
    kalshi_env: Literal["demo", "production"] = "demo"
    kalshi_api_key_id: SecretStr | None = None
    kalshi_private_key_path: Path | None = None
    kalshi_private_key: SecretStr | None = None
    darwin_live_trading_ack: str | None = None


def _deep_update(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def load_config(path: Path | None = None) -> DarwinConfig:
    settings = EnvironmentSettings()
    data: dict[str, Any] = {}
    config_path = path or Path("config") / f"{settings.darwin_env}.yaml"
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text()) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"config file {config_path} must contain a mapping")
        data = loaded

    env_overlay: dict[str, Any] = {
        "app": {"env": settings.darwin_env},
        "database": {"url": settings.database_url},
        "exchange": {
            "environment": settings.kalshi_env,
            "api_key_id": settings.kalshi_api_key_id,
            "private_key_path": settings.kalshi_private_key_path,
            "private_key": settings.kalshi_private_key,
        },
        "execution": {
            "mode": settings.trading_mode,
            "live_acknowledgement": settings.darwin_live_trading_ack,
        },
    }
    return DarwinConfig.model_validate(_deep_update(data, env_overlay))


def load_strategy_config(path: Path | None = None) -> StrategyConfig:
    if path is None:
        return StrategyConfig()
    loaded = yaml.safe_load(path.read_text()) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"strategy config {path} must contain a mapping")
    return StrategyConfig.model_validate(loaded)


def require_live_cli_flag(config: DarwinConfig, live_flag: bool) -> None:
    if config.execution.mode == TradingMode.LIVE and not live_flag:
        raise ValueError("live mode requires the CLI --live flag")


def env_summary() -> dict[str, str]:
    return {
        "DARWIN_ENV": os.getenv("DARWIN_ENV", "paper"),
        "TRADING_MODE": os.getenv("TRADING_MODE", "paper"),
        "KALSHI_ENV": os.getenv("KALSHI_ENV", "demo"),
    }

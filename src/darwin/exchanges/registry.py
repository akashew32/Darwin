from darwin.config import DarwinConfig
from darwin.exchanges.base import ExchangeClient
from darwin.exchanges.kalshi.client import KalshiClient


def build_exchange(config: DarwinConfig) -> ExchangeClient:
    if config.exchange.name == "kalshi":
        return KalshiClient.from_config(config.exchange)
    raise ValueError(f"unsupported exchange {config.exchange.name}")

from pathlib import Path

import pytest

from darwin.config import DarwinConfig, ExchangeConfig, ExecutionConfig, require_live_cli_flag
from darwin.domain.enums import TradingMode


def test_live_config_requires_ack() -> None:
    with pytest.raises(ValueError):
        ExecutionConfig(mode=TradingMode.LIVE)


def test_live_requires_cli_flag() -> None:
    config = DarwinConfig(
        exchange=ExchangeConfig(),
        execution=ExecutionConfig(
            mode=TradingMode.LIVE,
            live_acknowledgement="I_UNDERSTAND_LIVE_RISK",
        ),
    )
    with pytest.raises(ValueError):
        require_live_cli_flag(config, live_flag=False)


def test_credentials_are_not_required_for_paper() -> None:
    config = DarwinConfig()
    assert config.execution.mode == TradingMode.PAPER
    assert not config.exchange.has_credentials


def test_private_key_path_placeholder_is_not_secret() -> None:
    config = ExchangeConfig(private_key_path=Path("not-real.pem"))
    assert not config.has_credentials

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from darwin.config import RiskConfig
from darwin.domain.enums import Exchange, MarketStatus, OrderIntent, OutcomeSide
from darwin.domain.order import OrderRequest
from darwin.domain.portfolio import PortfolioState
from darwin.risk.engine import RiskContext, RiskEngine
from darwin.risk.kill_switch import KillSwitch


def order(quantity: int = 1, price: str = "0.50", client_id: str = "c1") -> OrderRequest:
    return OrderRequest(
        exchange=Exchange.KALSHI,
        market_id="M",
        outcome=OutcomeSide.YES,
        intent=OrderIntent.BUY,
        limit_price=Decimal(price),
        quantity=quantity,
        client_order_id=client_id,
        created_ts=datetime.now(UTC),
    )


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("spread", 0.50, "spread_limit"),
        ("data_age_seconds", 99.0, "stale_market_data"),
        ("estimated_slippage", Decimal("0.10"), "slippage_limit"),
        ("expected_net_edge", Decimal("-1"), "minimum_edge"),
        ("market_status", MarketStatus.CLOSED, "market_not_open"),
        ("database_healthy", False, "database_unhealthy"),
        ("feed_healthy", False, "feed_unhealthy"),
        ("position_mismatch", True, "position_mismatch"),
        ("exchange_error_count", 3, "exchange_error_circuit_breaker"),
        ("rejection_count", 5, "rejection_circuit_breaker"),
        ("daily_realized_pnl", Decimal("-101"), "daily_loss_limit"),
        ("drawdown", Decimal("-251"), "drawdown_limit"),
    ],
)
def test_risk_rejection_reasons(tmp_path, field: str, value: object, reason: str) -> None:
    context_kwargs = {
        "portfolio": PortfolioState(cash=Decimal("1000")),
        "open_orders": (),
        "spread": 0.01,
        "data_age_seconds": 0.0,
        "estimated_slippage": Decimal("0"),
        "expected_net_edge": Decimal("1"),
        "displayed_depth": 100,
    }
    context_kwargs[field] = value
    decision = RiskEngine(
        RiskConfig(min_available_cash=0), KillSwitch(tmp_path / "kill.json")
    ).check_order(order(), RiskContext(**context_kwargs), asof_ts=datetime.now(UTC))
    assert reason in decision.reasons


def test_open_order_limit_uses_open_orders_not_positions(tmp_path) -> None:
    request = order(client_id="open")
    open_order = __import__("darwin.domain.order", fromlist=["Order"]).Order.created(request)
    engine = RiskEngine(
        RiskConfig(max_open_orders=1, min_available_cash=0), KillSwitch(tmp_path / "kill.json")
    )
    decision = engine.check_order(
        order(client_id="new"),
        RiskContext(
            portfolio=PortfolioState(cash=Decimal("1000")),
            open_orders=(open_order,),
            expected_net_edge=Decimal("1"),
            displayed_depth=100,
        ),
        asof_ts=datetime.now(UTC),
    )
    assert "open_order_limit" in decision.reasons

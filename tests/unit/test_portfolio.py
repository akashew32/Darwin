from datetime import UTC, datetime
from decimal import Decimal

from darwin.domain.enums import Exchange, OrderIntent, OutcomeSide
from darwin.domain.fill import Fill
from darwin.domain.portfolio import PortfolioState
from darwin.portfolio.accounting import apply_fill_to_portfolio


def test_duplicate_fill_is_idempotent() -> None:
    fill = Fill(
        exchange=Exchange.KALSHI,
        fill_id="f1",
        market_id="M",
        client_order_id="c1",
        outcome=OutcomeSide.YES,
        intent=OrderIntent.BUY,
        price=Decimal("0.4"),
        quantity=10,
        fee=Decimal("0.01"),
        received_ts=datetime.now(UTC),
    )
    first = apply_fill_to_portfolio(PortfolioState(cash=Decimal("100")), fill)
    second = apply_fill_to_portfolio(first, fill)
    assert first == second
    assert second.positions["M"].yes_quantity == 10

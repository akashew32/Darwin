from datetime import UTC, datetime
from decimal import Decimal

import pytest

from darwin.domain.enums import Exchange, OrderIntent, OutcomeSide
from darwin.domain.fill import Fill
from darwin.domain.portfolio import PortfolioState
from darwin.portfolio.accounting import apply_fill_to_portfolio, settle_market


def fill(
    fill_id: str,
    outcome: OutcomeSide,
    intent: OrderIntent,
    price: str,
    quantity: int,
    fee: str = "0.01",
) -> Fill:
    return Fill(
        exchange=Exchange.KALSHI,
        fill_id=fill_id,
        market_id="M",
        client_order_id=f"c-{fill_id}",
        outcome=outcome,
        intent=intent,
        price=Decimal(price),
        quantity=quantity,
        fee=Decimal(fee),
        received_ts=datetime.now(UTC),
    )


@pytest.mark.parametrize("outcome", [OutcomeSide.YES, OutcomeSide.NO])
@pytest.mark.parametrize(
    "price,quantity,fee", [("0.25", 1, "0.01"), ("0.40", 3, "0.02"), ("0.70", 5, "0.03")]
)
def test_buy_cash_change_equals_notional_plus_fee(
    outcome: OutcomeSide, price: str, quantity: int, fee: str
) -> None:
    portfolio = PortfolioState(cash=Decimal("100"))
    updated = apply_fill_to_portfolio(
        portfolio, fill("f", outcome, OrderIntent.BUY, price, quantity, fee)
    )
    assert updated.cash == Decimal("100") - Decimal(price) * Decimal(quantity) - Decimal(fee)


@pytest.mark.parametrize(
    "sell_price,expected", [("0.35", Decimal("0.24")), ("0.55", Decimal("1.24"))]
)
def test_sell_realizes_pnl(sell_price: str, expected: Decimal) -> None:
    portfolio = apply_fill_to_portfolio(
        PortfolioState(cash=Decimal("100")),
        fill("buy", OutcomeSide.YES, OrderIntent.BUY, "0.30", 5, "0.01"),
    )
    updated = apply_fill_to_portfolio(
        portfolio,
        fill("sell", OutcomeSide.YES, OrderIntent.SELL, sell_price, 5, "0.01"),
    )
    assert updated.positions["M"].yes_quantity == 0
    assert updated.realized_pnl == expected


def test_settlement_pays_winner_and_expires_loser() -> None:
    portfolio = PortfolioState(cash=Decimal("100"))
    portfolio = apply_fill_to_portfolio(
        portfolio, fill("yes", OutcomeSide.YES, OrderIntent.BUY, "0.40", 2)
    )
    portfolio = apply_fill_to_portfolio(
        portfolio, fill("no", OutcomeSide.NO, OrderIntent.BUY, "0.30", 1)
    )
    settled = settle_market(portfolio, "M", yes_settles=True)
    assert settled.cash == portfolio.cash + Decimal("2")
    assert settled.positions["M"].settled
    assert settled.positions["M"].yes_quantity == 0


def test_cannot_sell_more_than_held() -> None:
    with pytest.raises(ValueError):
        apply_fill_to_portfolio(
            PortfolioState(cash=Decimal("100")),
            fill("sell", OutcomeSide.YES, OrderIntent.SELL, "0.50", 1),
        )

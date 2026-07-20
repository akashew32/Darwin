from datetime import UTC, datetime
from decimal import Decimal

import pytest

from darwin.domain.enums import Exchange, OrderIntent, OutcomeSide
from darwin.domain.fill import Fill
from darwin.domain.order import Order, OrderRequest
from darwin.domain.portfolio import PortfolioState
from darwin.portfolio.accounting import apply_fill_to_portfolio, apply_fill_with_closed_trade
from darwin.portfolio.equity import calculate_equity, release_for_order, reserve_for_order


def request(quantity: int = 5) -> OrderRequest:
    return OrderRequest(
        exchange=Exchange.KALSHI,
        market_id="M",
        outcome=OutcomeSide.YES,
        intent=OrderIntent.BUY,
        limit_price=Decimal("0.50"),
        quantity=quantity,
        client_order_id="reserve-test",
        created_ts=datetime.now(UTC),
    )


def make_fill(fid: str, side: OutcomeSide, intent: OrderIntent, price: str, qty: int) -> Fill:
    return Fill(
        exchange=Exchange.KALSHI,
        fill_id=fid,
        market_id="M",
        client_order_id=f"c-{fid}",
        outcome=side,
        intent=intent,
        price=Decimal(price),
        quantity=qty,
        fee=Decimal("0.01"),
        received_ts=datetime.now(UTC),
    )


@pytest.mark.parametrize(
    "side,mark,expected",
    [
        (OutcomeSide.YES, Decimal("0.60"), Decimal("100.19")),
        (OutcomeSide.NO, Decimal("0.60"), Decimal("99.99")),
    ],
)
def test_equity_marks_open_positions(side: OutcomeSide, mark: Decimal, expected: Decimal) -> None:
    portfolio = apply_fill_to_portfolio(
        PortfolioState(cash=Decimal("100")),
        make_fill("buy", side, OrderIntent.BUY, "0.40", 1),
    )
    assert calculate_equity(portfolio, {"M": mark}) == expected


@pytest.mark.parametrize("quantity", [1, 2, 5])
def test_reserved_cash_release_after_cancellation(quantity: int) -> None:
    order = Order.created(request(quantity=quantity))
    portfolio = reserve_for_order(PortfolioState(cash=Decimal("100")), order)
    assert portfolio.reserved_cash == Decimal(quantity) * Decimal("0.50")
    assert release_for_order(portfolio, order).reserved_cash == Decimal("0")


@pytest.mark.parametrize(
    "entry,exit_price,qty", [("0.30", "0.50", 1), ("0.25", "0.75", 2), ("0.60", "0.70", 3)]
)
def test_closed_trade_is_individual_not_cumulative(entry: str, exit_price: str, qty: int) -> None:
    portfolio = PortfolioState(cash=Decimal("100"))
    portfolio = apply_fill_to_portfolio(
        portfolio, make_fill("entry", OutcomeSide.YES, OrderIntent.BUY, entry, qty)
    )
    _, trade = apply_fill_with_closed_trade(
        portfolio, make_fill("exit", OutcomeSide.YES, OrderIntent.SELL, exit_price, qty)
    )
    assert trade is not None
    assert trade.net_realized_pnl == (Decimal(exit_price) - Decimal(entry)) * Decimal(
        qty
    ) - Decimal("0.01")


def test_late_duplicate_fill_is_ignored() -> None:
    portfolio = PortfolioState(cash=Decimal("100"))
    fill = make_fill("dup", OutcomeSide.YES, OrderIntent.BUY, "0.40", 1)
    first = apply_fill_to_portfolio(portfolio, fill)
    assert apply_fill_to_portfolio(first, fill) == first

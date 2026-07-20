from decimal import Decimal

import pytest

from darwin.backtest.metrics import max_drawdown, profit_factor, summarize
from darwin.exchanges.kalshi.mapper import cents_to_probability, probability_to_cents


@pytest.mark.parametrize("cents,probability", [(1, Decimal("0.01")), (25, Decimal("0.25")), (99, Decimal("0.99"))])
def test_cents_probability_conversion(cents: int, probability: Decimal) -> None:
    assert cents_to_probability(cents) == probability
    assert probability_to_cents(probability) == cents


@pytest.mark.parametrize(
    "equity,expected",
    [
        ([Decimal("100"), Decimal("99"), Decimal("101")], Decimal("-1")),
        ([Decimal("100"), Decimal("90"), Decimal("80")], Decimal("-20")),
        ([Decimal("100"), Decimal("101"), Decimal("102")], Decimal("0")),
    ],
)
def test_max_drawdown(equity: list[Decimal], expected: Decimal) -> None:
    assert max_drawdown(equity) == expected


@pytest.mark.parametrize(
    "pnls,expected",
    [
        ([Decimal("1"), Decimal("-0.5")], Decimal("2")),
        ([Decimal("2"), Decimal("-1"), Decimal("-1")], Decimal("1")),
    ],
)
def test_profit_factor(pnls: list[Decimal], expected: Decimal) -> None:
    assert profit_factor(pnls) == expected


def test_summary_includes_costs() -> None:
    summary = summarize(
        initial_cash=Decimal("100"),
        final_cash=Decimal("101"),
        realized_pnl=Decimal("1"),
        unrealized_pnl=Decimal("0"),
        fees=Decimal("0.1"),
        slippage=Decimal("0.2"),
        spread_cost=Decimal("0.3"),
        equity=[Decimal("100"), Decimal("101")],
        trade_pnls=[Decimal("1")],
        order_count=2,
        fill_count=1,
        cancellation_count=0,
    )
    assert summary["gross_pnl"] > summary["net_pnl"]
    assert summary["fill_rate"] == 0.5

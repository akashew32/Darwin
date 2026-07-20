from decimal import Decimal

from darwin.domain.fill import Fill
from darwin.domain.portfolio import PortfolioState
from darwin.portfolio.accounting import apply_fill_to_portfolio
from darwin.portfolio.pnl import mark_portfolio


class PortfolioManager:
    def __init__(self, initial_cash: Decimal) -> None:
        self.state = PortfolioState(cash=initial_cash)

    def apply_fill(self, fill: Fill) -> PortfolioState:
        self.state = apply_fill_to_portfolio(self.state, fill)
        return self.state

    def mark(self, marks: dict[str, Decimal]) -> PortfolioState:
        self.state = mark_portfolio(self.state, marks)
        return self.state

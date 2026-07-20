from decimal import Decimal

from darwin.domain.portfolio import PortfolioState


def mark_portfolio(portfolio: PortfolioState, marks: dict[str, Decimal]) -> PortfolioState:
    unrealized = Decimal("0")
    for market_id, position in portfolio.positions.items():
        if market_id in marks:
            unrealized += position.mark_unrealized(marks[market_id])
    return portfolio.model_copy(update={"unrealized_pnl": unrealized})

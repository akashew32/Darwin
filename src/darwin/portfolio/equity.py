from decimal import Decimal

from darwin.domain.enums import OrderIntent
from darwin.domain.order import Order
from darwin.domain.portfolio import PortfolioState


def calculate_equity(
    portfolio: PortfolioState,
    market_marks: dict[str, Decimal],
    open_orders: tuple[Order, ...] = (),
) -> Decimal:
    """Calculate marked account equity.

    Darwin accounting keeps cash reduced when positions are opened. Equity is therefore cash plus
    the current liquidation/mark value of open YES and NO positions. Reserved cash is included in
    cash but not available cash; open buy orders reserve additional cash only when the caller has
    represented it in `portfolio.reserved_cash`.
    """

    marked_positions = Decimal("0")
    for market_id, position in portfolio.positions.items():
        yes_mark = market_marks.get(market_id, Decimal("0.5"))
        no_mark = Decimal("1") - yes_mark
        marked_positions += Decimal(position.yes_quantity) * yes_mark
        marked_positions += Decimal(position.no_quantity) * no_mark
    pending_sell_value = Decimal("0")
    for order in open_orders:
        if order.request.intent == OrderIntent.SELL:
            pending_sell_value += Decimal(order.remaining_quantity) * order.request.limit_price
    return portfolio.cash + marked_positions + pending_sell_value


def reserve_for_order(portfolio: PortfolioState, order: Order) -> PortfolioState:
    if order.request.intent != OrderIntent.BUY:
        return portfolio
    reserve = Decimal(order.remaining_quantity) * order.request.limit_price
    return portfolio.model_copy(update={"reserved_cash": portfolio.reserved_cash + reserve})


def release_for_order(portfolio: PortfolioState, order: Order) -> PortfolioState:
    if order.request.intent != OrderIntent.BUY:
        return portfolio
    reserve = Decimal(order.remaining_quantity) * order.request.limit_price
    return portfolio.model_copy(
        update={"reserved_cash": max(Decimal("0"), portfolio.reserved_cash - reserve)}
    )

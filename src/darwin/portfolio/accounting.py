from decimal import Decimal

from darwin.domain.enums import OrderIntent, OutcomeSide
from darwin.domain.fill import Fill
from darwin.domain.portfolio import PortfolioState
from darwin.domain.position import Position


def apply_fill_to_portfolio(portfolio: PortfolioState, fill: Fill) -> PortfolioState:
    position = portfolio.positions.get(fill.market_id, Position(market_id=fill.market_id))
    if fill.fill_id in position.seen_fill_ids:
        return portfolio

    notional = fill.price * Decimal(fill.quantity)
    cash = portfolio.cash
    realized = position.realized_pnl
    yes_qty = position.yes_quantity
    no_qty = position.no_quantity
    avg_yes = position.average_yes_cost
    avg_no = position.average_no_cost

    if fill.intent == OrderIntent.BUY:
        cash -= notional + fill.fee
        if fill.outcome == OutcomeSide.YES:
            avg_yes = _weighted_average(avg_yes, yes_qty, fill.price, fill.quantity)
            yes_qty += fill.quantity
        else:
            avg_no = _weighted_average(avg_no, no_qty, fill.price, fill.quantity)
            no_qty += fill.quantity
    else:
        cash += notional - fill.fee
        if fill.outcome == OutcomeSide.YES:
            if fill.quantity > yes_qty:
                raise ValueError("cannot sell more YES contracts than held")
            realized += (fill.price - avg_yes) * Decimal(fill.quantity) - fill.fee
            yes_qty -= fill.quantity
        else:
            if fill.quantity > no_qty:
                raise ValueError("cannot sell more NO contracts than held")
            realized += (fill.price - avg_no) * Decimal(fill.quantity) - fill.fee
            no_qty -= fill.quantity

    new_position = position.model_copy(
        update={
            "yes_quantity": yes_qty,
            "no_quantity": no_qty,
            "average_yes_cost": avg_yes if yes_qty else Decimal("0"),
            "average_no_cost": avg_no if no_qty else Decimal("0"),
            "realized_pnl": realized,
            "fees": position.fees + fill.fee,
            "seen_fill_ids": position.seen_fill_ids | {fill.fill_id},
        }
    )
    positions = dict(portfolio.positions)
    positions[fill.market_id] = new_position
    return portfolio.model_copy(
        update={
            "cash": cash,
            "positions": positions,
            "fees": portfolio.fees + fill.fee,
            "realized_pnl": sum((p.realized_pnl for p in positions.values()), Decimal("0")),
        }
    )


def settle_market(
    portfolio: PortfolioState,
    market_id: str,
    *,
    yes_settles: bool,
) -> PortfolioState:
    position = portfolio.positions.get(market_id)
    if position is None or position.settled:
        return portfolio
    payout = Decimal(position.yes_quantity if yes_settles else position.no_quantity)
    cost_basis = (
        Decimal(position.yes_quantity) * position.average_yes_cost
        + Decimal(position.no_quantity) * position.average_no_cost
    )
    realized = position.realized_pnl + payout - cost_basis
    new_position = position.model_copy(
        update={
            "yes_quantity": 0,
            "no_quantity": 0,
            "average_yes_cost": Decimal("0"),
            "average_no_cost": Decimal("0"),
            "realized_pnl": realized,
            "settled": True,
        }
    )
    positions = dict(portfolio.positions)
    positions[market_id] = new_position
    return portfolio.model_copy(
        update={
            "cash": portfolio.cash + payout,
            "positions": positions,
            "realized_pnl": sum((p.realized_pnl for p in positions.values()), Decimal("0")),
            "unrealized_pnl": Decimal("0"),
        }
    )


def _weighted_average(old_price: Decimal, old_qty: int, price: Decimal, qty: int) -> Decimal:
    if old_qty + qty <= 0:
        return Decimal("0")
    return ((old_price * Decimal(old_qty)) + (price * Decimal(qty))) / Decimal(old_qty + qty)

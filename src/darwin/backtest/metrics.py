from decimal import Decimal
from statistics import mean
from typing import Any


def max_drawdown(equity: list[Decimal]) -> Decimal:
    if not equity:
        return Decimal("0")
    peak = equity[0]
    drawdown = Decimal("0")
    for value in equity:
        peak = max(peak, value)
        drawdown = min(drawdown, value - peak)
    return drawdown


def profit_factor(pnls: list[Decimal]) -> Decimal:
    gains = sum((p for p in pnls if p > 0), Decimal("0"))
    losses = abs(sum((p for p in pnls if p < 0), Decimal("0")))
    if losses == 0:
        return Decimal("0")
    return gains / losses


def win_rate(pnls: list[Decimal]) -> float:
    if not pnls:
        return 0.0
    return mean(1.0 if p > 0 else 0.0 for p in pnls)


def summarize(
    *,
    initial_cash: Decimal,
    final_cash: Decimal,
    realized_pnl: Decimal,
    unrealized_pnl: Decimal,
    fees: Decimal,
    slippage: Decimal,
    spread_cost: Decimal,
    equity: list[Decimal],
    trade_pnls: list[Decimal],
    order_count: int,
    fill_count: int,
    cancellation_count: int,
) -> dict[str, Any]:
    net_pnl = final_cash + unrealized_pnl - initial_cash
    gross_pnl = net_pnl + fees + slippage + spread_cost
    return {
        "initial_cash": float(initial_cash),
        "final_cash": float(final_cash),
        "gross_pnl": float(gross_pnl),
        "net_pnl": float(net_pnl),
        "realized_pnl": float(realized_pnl),
        "unrealized_pnl": float(unrealized_pnl),
        "fees": float(fees),
        "estimated_slippage": float(slippage),
        "spread_cost": float(spread_cost),
        "return_on_initial_capital": float(net_pnl / initial_cash) if initial_cash else 0.0,
        "max_drawdown": float(max_drawdown(equity)),
        "win_rate": win_rate(trade_pnls),
        "average_win": float(mean([p for p in trade_pnls if p > 0]))
        if any(p > 0 for p in trade_pnls)
        else 0.0,
        "average_loss": float(mean([p for p in trade_pnls if p < 0]))
        if any(p < 0 for p in trade_pnls)
        else 0.0,
        "profit_factor": float(profit_factor(trade_pnls)),
        "turnover": order_count,
        "order_count": order_count,
        "fill_count": fill_count,
        "fill_rate": fill_count / order_count if order_count else 0.0,
        "cancellation_rate": cancellation_count / order_count if order_count else 0.0,
        "average_holding_period_seconds": 0.0,
    }

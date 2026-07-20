from decimal import Decimal
from statistics import mean


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

from decimal import Decimal


def fixed_slippage(price: Decimal, bps: int) -> Decimal:
    adjustment = Decimal(bps) / Decimal("10000")
    return min(Decimal("0.99"), max(Decimal("0.01"), price + adjustment))

from decimal import Decimal


def fixed_contract_size(default_size: int, max_size: int) -> int:
    return max(0, min(default_size, max_size))


def edge_weighted_size(edge: Decimal, base_size: int, max_size: int) -> int:
    if edge <= 0:
        return 0
    scaled = int(Decimal(base_size) * min(Decimal("3"), edge / Decimal("0.02")))
    return max(1, min(scaled, max_size))


def fractional_kelly_size(
    *, probability: Decimal, price: Decimal, capital: Decimal, fraction: Decimal, cap: int
) -> int:
    edge = probability - price
    if edge <= 0:
        return 0
    odds = (Decimal("1") - price) / price
    kelly = edge / odds
    dollars = max(Decimal("0"), capital * kelly * fraction)
    return min(int(dollars / price), cap)

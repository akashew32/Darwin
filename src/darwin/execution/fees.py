from decimal import Decimal


def kalshi_fee_estimate(
    price: Decimal, quantity: int, fee_rate: Decimal = Decimal("0.0007")
) -> Decimal:
    return (price * (Decimal("1") - price) * Decimal(quantity) * fee_rate).quantize(
        Decimal("0.0001")
    )

from darwin.domain.market import Market


def market_accepts_orders(market: Market) -> bool:
    return market.accepts_orders

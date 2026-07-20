from decimal import Decimal

from darwin.domain.orderbook import OrderBookSnapshot


def spread(snapshot: OrderBookSnapshot) -> float | None:
    if snapshot.best_bid is None or snapshot.best_ask is None:
        return None
    return float(snapshot.best_ask - snapshot.best_bid)


def microprice(snapshot: OrderBookSnapshot) -> Decimal | None:
    if not snapshot.bids or not snapshot.asks:
        return None
    bid = snapshot.bids[0]
    ask = snapshot.asks[0]
    denom = bid.quantity + ask.quantity
    if denom <= 0:
        return None
    return (ask.price * Decimal(bid.quantity) + bid.price * Decimal(ask.quantity)) / Decimal(denom)


def depth_imbalance(snapshot: OrderBookSnapshot, levels: int = 3) -> float:
    bid_depth = sum(level.quantity for level in snapshot.bids[:levels])
    ask_depth = sum(level.quantity for level in snapshot.asks[:levels])
    total = bid_depth + ask_depth
    if total == 0:
        return 0.0
    return (bid_depth - ask_depth) / total

from darwin.domain.orderbook import OrderBookSnapshot


def top_depth(snapshot: OrderBookSnapshot, levels: int = 1) -> int:
    return sum(level.quantity for level in snapshot.bids[:levels]) + sum(
        level.quantity for level in snapshot.asks[:levels]
    )

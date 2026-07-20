from darwin.domain.order import Order


def find_unknown_orders(local: list[Order], remote_exchange_ids: set[str]) -> list[Order]:
    return [
        order
        for order in local
        if order.exchange_order_id and order.exchange_order_id not in remote_exchange_ids
    ]

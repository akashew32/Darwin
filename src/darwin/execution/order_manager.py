from darwin.domain.order import Order, OrderRequest


class OrderManager:
    def __init__(self) -> None:
        self.orders: dict[str, Order] = {}

    def create(self, request: OrderRequest) -> Order:
        if request.client_order_id in self.orders:
            return self.orders[request.client_order_id]
        order = Order.created(request)
        self.orders[request.client_order_id] = order
        return order

    def update(self, order: Order) -> None:
        self.orders[order.request.client_order_id] = order

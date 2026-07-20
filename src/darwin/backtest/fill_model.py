from darwin.domain.order import Order, OrderRequest
from darwin.domain.orderbook import OrderBookSnapshot
from darwin.execution.simulated_broker import SimulatedBroker


class ConservativeTouchFillModel:
    def __init__(self) -> None:
        self.broker = SimulatedBroker()

    def apply(self, request: OrderRequest, snapshot: OrderBookSnapshot) -> Order:
        return self.broker.submit_against_snapshot(request, snapshot, snapshot.received_ts)

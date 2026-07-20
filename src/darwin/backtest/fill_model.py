from darwin.domain.order import OrderRequest
from darwin.domain.orderbook import OrderBookSnapshot
from darwin.execution.simulated_broker import FillSimulationResult, SimulatedBroker


class ConservativeTouchFillModel:
    def __init__(self) -> None:
        self.broker = SimulatedBroker()

    def apply(self, request: OrderRequest, snapshot: OrderBookSnapshot) -> FillSimulationResult:
        return self.broker.submit_against_snapshot(request, snapshot, snapshot.received_ts)

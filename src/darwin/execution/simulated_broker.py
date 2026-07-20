from datetime import datetime

from darwin.domain.enums import OrderIntent
from darwin.domain.fill import Fill
from darwin.domain.order import Order, OrderRequest
from darwin.domain.orderbook import OrderBookSnapshot
from darwin.execution.fees import kalshi_fee_estimate
from darwin.execution.state_machine import apply_fill


class SimulatedBroker:
    def submit_against_snapshot(
        self, request: OrderRequest, snapshot: OrderBookSnapshot, ts: datetime
    ) -> Order:
        order = Order.created(request)
        executable = False
        if request.intent == OrderIntent.BUY and snapshot.best_ask is not None:
            executable = request.limit_price >= snapshot.best_ask
            fill_price = snapshot.best_ask
        elif request.intent == OrderIntent.SELL and snapshot.best_bid is not None:
            executable = request.limit_price <= snapshot.best_bid
            fill_price = snapshot.best_bid
        else:
            fill_price = request.limit_price
        if not executable:
            return order
        fill = Fill(
            exchange=request.exchange,
            fill_id=f"sim-{request.client_order_id}",
            market_id=request.market_id,
            client_order_id=request.client_order_id,
            outcome=request.outcome,
            intent=request.intent,
            price=fill_price,
            quantity=request.quantity,
            fee=kalshi_fee_estimate(fill_price, request.quantity),
            received_ts=ts,
        )
        return apply_fill(order, fill)

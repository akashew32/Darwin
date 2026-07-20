from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from darwin.domain.enums import OrderIntent
from darwin.domain.fill import Fill
from darwin.domain.order import Order, OrderRequest
from darwin.domain.orderbook import OrderBookSnapshot, PriceLevel
from darwin.execution.fees import kalshi_fee_estimate
from darwin.execution.state_machine import apply_fill


@dataclass(frozen=True)
class FillSimulationResult:
    order: Order
    fills: tuple[Fill, ...]
    slippage: Decimal
    spread_cost: Decimal
    missed_quantity: int


class SimulatedBroker:
    """Event-driven broker with visible-book execution and partial fills."""

    def submit_against_snapshot(
        self,
        request: OrderRequest,
        snapshot: OrderBookSnapshot,
        ts: datetime,
        *,
        max_depth_participation: Decimal = Decimal("0.5"),
        slippage_bps: int = 0,
    ) -> FillSimulationResult:
        order = Order.created(request)
        levels = self._executable_levels(request, snapshot)
        if not levels:
            return FillSimulationResult(order, (), Decimal("0"), Decimal("0"), request.quantity)

        remaining = request.quantity
        fills: list[Fill] = []
        slippage = Decimal("0")
        spread_cost = Decimal("0")
        mid = snapshot.midprice or request.limit_price

        for index, level in enumerate(levels):
            if remaining <= 0:
                break
            executable = (
                request.intent == OrderIntent.BUY and level.price <= request.limit_price
            ) or (request.intent == OrderIntent.SELL and level.price >= request.limit_price)
            if not executable:
                break
            max_at_level = max(1, int(Decimal(level.quantity) * max_depth_participation))
            quantity = min(remaining, max_at_level)
            price = self._apply_slippage(level.price, request.intent, slippage_bps)
            fill = Fill(
                exchange=request.exchange,
                fill_id=f"sim-{request.client_order_id}-{index}",
                market_id=request.market_id,
                client_order_id=request.client_order_id,
                outcome=request.outcome,
                intent=request.intent,
                price=price,
                quantity=quantity,
                fee=kalshi_fee_estimate(price, quantity),
                received_ts=ts,
            )
            fills.append(fill)
            order = apply_fill(order, fill)
            remaining -= quantity
            slippage += abs(price - level.price) * Decimal(quantity)
            spread_cost += abs(price - mid) * Decimal(quantity)

        return FillSimulationResult(order, tuple(fills), slippage, spread_cost, remaining)

    def _executable_levels(
        self,
        request: OrderRequest,
        snapshot: OrderBookSnapshot,
    ) -> tuple[PriceLevel, ...]:
        if request.intent == OrderIntent.BUY:
            return snapshot.asks
        return snapshot.bids

    def _apply_slippage(self, price: Decimal, intent: OrderIntent, bps: int) -> Decimal:
        if bps == 0:
            return price
        adjustment = Decimal(bps) / Decimal("10000")
        if intent == OrderIntent.BUY:
            return min(Decimal("0.99"), price + adjustment)
        return max(Decimal("0.01"), price - adjustment)

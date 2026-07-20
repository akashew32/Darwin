from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from darwin.config import RiskConfig
from darwin.domain.enums import MarketStatus, RiskDecisionType
from darwin.domain.order import Order, OrderRequest
from darwin.domain.portfolio import PortfolioState
from darwin.domain.signal import RiskDecision
from darwin.risk.kill_switch import KillSwitch


@dataclass(frozen=True)
class RiskContext:
    portfolio: PortfolioState
    open_orders: tuple[Order, ...]
    market_status: MarketStatus = MarketStatus.OPEN
    spread: float = 0.0
    data_age_seconds: float = 0.0
    estimated_slippage: Decimal = Decimal("0")
    expected_net_edge: Decimal = Decimal("0")
    displayed_depth: int = 0
    drawdown: Decimal = Decimal("0")
    daily_realized_pnl: Decimal = Decimal("0")
    database_healthy: bool = True
    feed_healthy: bool = True
    position_mismatch: bool = False
    exchange_error_count: int = 0
    rejection_count: int = 0


class RiskEngine:
    def __init__(self, config: RiskConfig, kill_switch: KillSwitch) -> None:
        self.config = config
        self.kill_switch = kill_switch
        self.seen_client_ids: set[str] = set()

    def check_order(
        self,
        order: OrderRequest,
        context: RiskContext,
        *,
        asof_ts: datetime,
    ) -> RiskDecision:
        reasons: list[str] = []
        portfolio = context.portfolio
        position = portfolio.positions.get(order.market_id)
        current_qty = 0 if position is None else abs(position.net_yes_exposure)
        open_qty = sum(
            o.remaining_quantity
            for o in context.open_orders
            if o.request.market_id == order.market_id
        )
        notional = order.limit_price * Decimal(order.quantity)

        if self.kill_switch.active():
            reasons.append("kill_switch_active")
        if order.client_order_id in self.seen_client_ids:
            reasons.append("duplicate_client_order_id")
        if order.quantity > self.config.max_order_size:
            reasons.append("order_size_limit")
        if current_qty + open_qty + order.quantity > self.config.max_position_per_market:
            reasons.append("market_position_limit")
        if portfolio.gross_contracts + open_qty + order.quantity > self.config.max_gross_contracts:
            reasons.append("gross_exposure_limit")
        if len(context.open_orders) >= self.config.max_open_orders:
            reasons.append("open_order_limit")
        if portfolio.available_cash < Decimal(str(self.config.min_available_cash)):
            reasons.append("minimum_cash")
        if notional > portfolio.available_cash:
            reasons.append("insufficient_cash_for_notional")
        if context.spread > self.config.max_spread:
            reasons.append("spread_limit")
        if context.data_age_seconds > self.config.max_market_data_age_seconds:
            reasons.append("stale_market_data")
        if context.estimated_slippage > Decimal(str(self.config.max_estimated_slippage)):
            reasons.append("slippage_limit")
        if context.expected_net_edge < Decimal(str(self.config.min_expected_edge)):
            reasons.append("minimum_edge")
        if context.displayed_depth and order.quantity > max(1, int(context.displayed_depth * 0.5)):
            reasons.append("depth_participation_limit")
        if context.market_status != MarketStatus.OPEN:
            reasons.append("market_not_open")
        if order.limit_price <= Decimal("0.01") or order.limit_price >= Decimal("0.99"):
            reasons.append("fat_finger_price")
        if not context.database_healthy:
            reasons.append("database_unhealthy")
        if not context.feed_healthy:
            reasons.append("feed_unhealthy")
        if context.position_mismatch:
            reasons.append("position_mismatch")
        if context.exchange_error_count >= self.config.exchange_error_limit:
            reasons.append("exchange_error_circuit_breaker")
        if context.rejection_count >= self.config.rejection_limit:
            reasons.append("rejection_circuit_breaker")
        if context.daily_realized_pnl <= -Decimal(str(self.config.daily_loss_limit)):
            reasons.append("daily_loss_limit")
        if context.drawdown <= -Decimal(str(self.config.max_drawdown)):
            reasons.append("drawdown_limit")

        decision = RiskDecisionType.REJECTED if reasons else RiskDecisionType.APPROVED
        if not reasons:
            self.seen_client_ids.add(order.client_order_id)
        return RiskDecision(decision=decision, asof_ts=asof_ts, order=order, reasons=tuple(reasons))

    def check(
        self,
        order: OrderRequest,
        portfolio: PortfolioState,
        *,
        spread: float,
        data_age_seconds: float,
        expected_edge: Decimal,
        asof_ts: datetime,
    ) -> RiskDecision:
        return self.check_order(
            order,
            RiskContext(
                portfolio=portfolio,
                open_orders=(),
                spread=spread,
                data_age_seconds=data_age_seconds,
                expected_net_edge=expected_edge,
            ),
            asof_ts=asof_ts,
        )

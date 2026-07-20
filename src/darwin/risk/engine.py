from datetime import datetime
from decimal import Decimal

from darwin.config import RiskConfig
from darwin.domain.enums import RiskDecisionType
from darwin.domain.order import OrderRequest
from darwin.domain.portfolio import PortfolioState
from darwin.domain.signal import RiskDecision
from darwin.risk.kill_switch import KillSwitch


class RiskEngine:
    def __init__(self, config: RiskConfig, kill_switch: KillSwitch) -> None:
        self.config = config
        self.kill_switch = kill_switch
        self.seen_client_ids: set[str] = set()

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
        reasons: list[str] = []
        if self.kill_switch.active():
            reasons.append("kill_switch_active")
        if order.client_order_id in self.seen_client_ids:
            reasons.append("duplicate_client_order_id")
        if order.quantity > self.config.max_order_size:
            reasons.append("order_size_limit")
        if portfolio.gross_contracts + order.quantity > self.config.max_gross_contracts:
            reasons.append("gross_exposure_limit")
        if len(portfolio.positions) > self.config.max_open_orders:
            reasons.append("open_order_limit")
        if spread > self.config.max_spread:
            reasons.append("spread_limit")
        if data_age_seconds > self.config.max_market_data_age_seconds:
            reasons.append("stale_market_data")
        if portfolio.available_cash < Decimal(str(self.config.min_available_cash)):
            reasons.append("minimum_cash")
        if expected_edge < Decimal(str(self.config.min_expected_edge)):
            reasons.append("minimum_edge")
        decision = RiskDecisionType.REJECTED if reasons else RiskDecisionType.APPROVED
        if not reasons:
            self.seen_client_ids.add(order.client_order_id)
        return RiskDecision(decision=decision, asof_ts=asof_ts, order=order, reasons=tuple(reasons))

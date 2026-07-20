from darwin.domain.portfolio import PortfolioState
from darwin.domain.signal import Signal
from darwin.risk.engine import RiskEngine


class ExecutionEngine:
    def __init__(self, risk: RiskEngine, portfolio: PortfolioState) -> None:
        self.risk = risk
        self.portfolio = portfolio

    def approve_signal(self, signal: Signal, *, spread: float, data_age_seconds: float) -> bool:
        if signal.order is None:
            return False
        decision = self.risk.check(
            signal.order,
            self.portfolio,
            spread=spread,
            data_age_seconds=data_age_seconds,
            expected_edge=signal.expected_edge,
            asof_ts=signal.asof_ts,
        )
        return decision.decision.value == "approved"

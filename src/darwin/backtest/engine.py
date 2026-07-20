from decimal import Decimal

from darwin.backtest.events import MarketDataEvent
from darwin.backtest.fill_model import ConservativeTouchFillModel
from darwin.domain.order import Order
from darwin.domain.signal import Signal
from darwin.features.pipeline import FeaturePipeline
from darwin.portfolio.manager import PortfolioManager
from darwin.strategies.base import Strategy


class BacktestEngine:
    def __init__(self, strategy: Strategy, initial_cash: Decimal = Decimal("10000")) -> None:
        self.strategy = strategy
        self.features = FeaturePipeline()
        self.fill_model = ConservativeTouchFillModel()
        self.portfolio = PortfolioManager(initial_cash)
        self.signals: list[Signal] = []
        self.orders: list[Order] = []

    def run(self, events: list[MarketDataEvent]) -> dict[str, object]:
        for event in sorted(events, key=lambda e: e.snapshot.received_ts):
            vector = self.features.from_snapshot(event.snapshot)
            signal = self.strategy.generate(vector)
            self.signals.append(signal)
            if signal.order:
                order = self.fill_model.apply(signal.order, event.snapshot)
                self.orders.append(order)
        return {
            "signals": self.signals,
            "orders": self.orders,
            "portfolio": self.portfolio.state,
        }

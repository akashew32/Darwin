from darwin.domain.enums import TradingMode
from darwin.execution.paper_broker import PaperBroker
from darwin.execution.simulated_broker import SimulatedBroker


def build_broker(mode: TradingMode) -> SimulatedBroker:
    if mode == TradingMode.PAPER:
        return PaperBroker()
    if mode == TradingMode.BACKTEST:
        return SimulatedBroker()
    raise ValueError("live broker must be constructed through guarded LiveBroker")

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from darwin.backtest.events import (
    BacktestEvent,
    delta_from_event,
    read_events,
    snapshot_from_event,
    status_from_event,
)
from darwin.backtest.metrics import summarize
from darwin.backtest.reporting import write_outputs
from darwin.config import RiskConfig, StrategyConfig
from darwin.domain.enums import MarketStatus, OrderStatus
from darwin.domain.market import Market
from darwin.domain.portfolio import PortfolioState
from darwin.exchanges.kalshi.orderbook import LocalOrderBook
from darwin.execution.order_manager import OrderManager
from darwin.execution.simulated_broker import SimulatedBroker
from darwin.features.pipeline import StatefulFeaturePipeline
from darwin.portfolio.accounting import apply_fill_with_closed_trade, settle_market
from darwin.portfolio.equity import calculate_equity
from darwin.portfolio.pnl import mark_portfolio
from darwin.risk.engine import RiskContext, RiskEngine
from darwin.risk.kill_switch import KillSwitch
from darwin.strategies.base import StrategyContext
from darwin.strategies.momentum import MomentumStrategy


class BacktestEngine:
    def __init__(
        self,
        *,
        strategy_config: StrategyConfig,
        risk_config: RiskConfig,
        initial_cash: Decimal = Decimal("10000"),
        output: Path | None = None,
        seed: int = 42,
    ) -> None:
        self.strategy = MomentumStrategy(strategy_config)
        self.risk = RiskEngine(risk_config, KillSwitch(risk_config.kill_switch_path))
        self.features = StatefulFeaturePipeline()
        self.broker = SimulatedBroker()
        self.order_manager = OrderManager()
        self.portfolio = PortfolioState(cash=initial_cash)
        self.initial_cash = initial_cash
        self.output = output
        self.seed = seed
        self.books: dict[str, LocalOrderBook] = {}
        self.market_status: dict[str, MarketStatus] = {}
        self.rows: dict[str, list[dict[str, Any]]] = {
            "trades": [],
            "orders": [],
            "fills": [],
            "signals": [],
            "equity_curve": [],
            "positions": [],
            "risk_decisions": [],
        }
        self.slippage = Decimal("0")
        self.spread_cost = Decimal("0")

    @classmethod
    def from_replay(
        cls,
        input_path: Path,
        *,
        strategy_config: StrategyConfig,
        risk_config: RiskConfig,
        initial_cash: Decimal,
        output: Path | None = None,
        seed: int = 42,
    ) -> dict[str, Any]:
        engine = cls(
            strategy_config=strategy_config,
            risk_config=risk_config,
            initial_cash=initial_cash,
            output=output,
            seed=seed,
        )
        return engine.run(read_events(str(input_path)))

    def run(self, events: list[BacktestEvent]) -> dict[str, Any]:
        for event in events:
            self._handle_event(event)

        equity = [Decimal(str(row["equity"])) for row in self.rows["equity_curve"]]
        trade_pnls = [Decimal(str(row["net_realized_pnl"])) for row in self.rows["trades"]]
        summary = summarize(
            initial_cash=self.initial_cash,
            final_cash=self.portfolio.cash,
            realized_pnl=self.portfolio.realized_pnl,
            unrealized_pnl=self.portfolio.unrealized_pnl,
            fees=self.portfolio.fees,
            slippage=self.slippage,
            spread_cost=self.spread_cost,
            equity=equity,
            trade_pnls=trade_pnls,
            order_count=len(self.rows["orders"]),
            fill_count=len(self.rows["fills"]),
            cancellation_count=sum(
                1 for row in self.rows["orders"] if row.get("status") == OrderStatus.CANCELED.value
            ),
        )
        result: dict[str, Any] = {"summary": summary, **self.rows}
        if self.output is not None:
            write_outputs(
                self.output,
                result,
                {"initial_cash": float(self.initial_cash), "seed": self.seed},
            )
        return result

    def _handle_event(self, event: BacktestEvent) -> None:
        if event.event_type == "orderbook_snapshot":
            snapshot = snapshot_from_event(event)
            book = self.books.setdefault(event.market_id, LocalOrderBook())
            book.apply_snapshot(snapshot)
            self.market_status.setdefault(event.market_id, MarketStatus.OPEN)
            self._decide(event, snapshot)
        elif event.event_type == "orderbook_delta":
            book = self.books[event.market_id]
            snapshot = book.apply_delta(delta_from_event(event))
            self._decide(event, snapshot)
        elif event.event_type == "market_status":
            self.market_status[event.market_id] = status_from_event(event)
        elif event.event_type == "settlement":
            self.portfolio = settle_market(
                self.portfolio,
                event.market_id,
                yes_settles=bool(event.payload.get("yes_settles", True)),
            )
            self._record_equity(event)

    def _decide(self, event: BacktestEvent, snapshot: Any) -> None:
        vector = self.features.update(snapshot)
        if "momentum" in event.payload:
            vector = vector.model_copy(
                update={"values": vector.values | {"momentum": float(event.payload["momentum"])}}
            )
        marks = {event.market_id: snapshot.midprice or Decimal("0.5")}
        self.portfolio = mark_portfolio(self.portfolio, marks)
        position = self.portfolio.positions.get(event.market_id)
        decision = self.strategy.decide(
            vector,
            StrategyContext(
                market=Market(
                    exchange=snapshot.exchange,
                    market_id=event.market_id,
                    event_id=event.payload.get("event_id", "synthetic"),
                    title=event.payload.get("title", event.market_id),
                    status=self.market_status.get(event.market_id, MarketStatus.OPEN),
                    close_time=event.received_ts + timedelta(days=1),
                ),
                position=position,
                open_orders=tuple(self.order_manager.open_orders()),
                unrealized_pnl=Decimal("0")
                if position is None
                else position.mark_unrealized(marks[event.market_id]),
                now=event.received_ts,
            ),
        )
        self.rows["signals"].append(
            {
                "ts": event.received_ts.isoformat(),
                "market_id": event.market_id,
                "action": decision.action,
                "score": decision.score,
                "net_edge": float(decision.net_edge),
                "reasons": "|".join(decision.reasons),
            }
        )
        for order_request in decision.proposed_orders:
            risk_decision = self.risk.check_order(
                order_request,
                RiskContext(
                    portfolio=self.portfolio,
                    open_orders=tuple(self.order_manager.open_orders()),
                    market_status=self.market_status.get(event.market_id, MarketStatus.OPEN),
                    spread=vector.values["spread"],
                    data_age_seconds=vector.values.get("data_age_seconds", 0.0),
                    estimated_slippage=decision.estimated_slippage,
                    expected_net_edge=decision.net_edge,
                    displayed_depth=int(vector.values.get("top_depth", 0)),
                    daily_realized_pnl=self.portfolio.realized_pnl,
                ),
                asof_ts=event.received_ts,
            )
            self.rows["risk_decisions"].append(
                {
                    "ts": event.received_ts.isoformat(),
                    "client_order_id": order_request.client_order_id,
                    "decision": risk_decision.decision.value,
                    "reasons": "|".join(risk_decision.reasons),
                }
            )
            if risk_decision.decision.value != "approved":
                continue
            self.order_manager.create(order_request, correlation_id=f"event-{event.input_index}")
            fill_result = self.broker.submit_against_snapshot(
                order_request,
                snapshot,
                event.received_ts,
                slippage_bps=5,
            )
            self.order_manager.orders[order_request.client_order_id] = fill_result.order
            self.slippage += fill_result.slippage
            self.spread_cost += fill_result.spread_cost
            self.rows["orders"].append(
                {
                    "ts": event.received_ts.isoformat(),
                    "client_order_id": order_request.client_order_id,
                    "market_id": event.market_id,
                    "intent": order_request.intent.value,
                    "outcome": order_request.outcome.value,
                    "quantity": order_request.quantity,
                    "limit_price": float(order_request.limit_price),
                    "status": fill_result.order.status.value,
                    "filled_quantity": fill_result.order.filled_quantity,
                }
            )
            for fill in fill_result.fills:
                self.order_manager.apply_fill(fill)
                self.portfolio, closed_trade = apply_fill_with_closed_trade(
                    self.portfolio, fill, exit_reason="strategy_exit"
                )
                self.rows["fills"].append(
                    {
                        "ts": fill.received_ts.isoformat(),
                        "fill_id": fill.fill_id,
                        "client_order_id": fill.client_order_id,
                        "market_id": fill.market_id,
                        "intent": fill.intent.value,
                        "outcome": fill.outcome.value,
                        "price": float(fill.price),
                        "quantity": fill.quantity,
                        "fee": float(fill.fee),
                    }
                )
                if closed_trade is not None:
                    self.rows["trades"].append(
                        {
                            "entry_ts": closed_trade.entry_ts.isoformat(),
                            "exit_ts": closed_trade.exit_ts.isoformat(),
                            "market_id": closed_trade.market_id,
                            "outcome": closed_trade.outcome.value,
                            "quantity": closed_trade.quantity,
                            "average_entry_price": float(closed_trade.average_entry_price),
                            "average_exit_price": float(closed_trade.average_exit_price),
                            "gross_realized_pnl": float(closed_trade.gross_realized_pnl),
                            "fees": float(closed_trade.fees),
                            "slippage": float(closed_trade.slippage),
                            "net_realized_pnl": float(closed_trade.net_realized_pnl),
                            "holding_seconds": closed_trade.holding_seconds,
                            "exit_reason": closed_trade.exit_reason,
                        }
                    )
        self._record_equity(event)

    def _record_equity(self, event: BacktestEvent) -> None:
        marks = {
            market_id: book.current_snapshot().midprice or Decimal("0.5")
            for market_id, book in self.books.items()
            if book.snapshot is not None
        }
        equity = calculate_equity(self.portfolio, marks, tuple(self.order_manager.open_orders()))
        self.rows["equity_curve"].append(
            {
                "ts": event.received_ts.isoformat(),
                "cash": float(self.portfolio.cash),
                "unrealized_pnl": float(self.portfolio.unrealized_pnl),
                "equity": float(equity),
            }
        )
        for market_id, position in self.portfolio.positions.items():
            self.rows["positions"].append(
                {
                    "ts": event.received_ts.isoformat(),
                    "market_id": market_id,
                    "yes_quantity": position.yes_quantity,
                    "no_quantity": position.no_quantity,
                    "average_yes_cost": float(position.average_yes_cost),
                    "average_no_cost": float(position.average_no_cost),
                    "realized_pnl": float(position.realized_pnl),
                    "fees": float(position.fees),
                    "settled": position.settled,
                }
            )

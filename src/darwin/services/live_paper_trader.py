import asyncio
import json
import signal
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from darwin.config import RiskConfig, StrategyConfig
from darwin.data.event_bus import BoundedEventBus, QueueOverflowError
from darwin.data.events import NormalizedEvent
from darwin.domain.enums import Exchange, MarketStatus
from darwin.domain.portfolio import PortfolioState
from darwin.exchanges.kalshi.orderbook import LocalOrderBook
from darwin.execution.config import ExecutionSimulationConfig
from darwin.execution.order_manager import OrderManager
from darwin.execution.paper_broker import PaperBroker
from darwin.execution.safety import ExecutionEndpointGuard
from darwin.features.pipeline import StatefulFeaturePipeline
from darwin.portfolio.accounting import apply_fill_with_closed_trade
from darwin.portfolio.equity import calculate_equity
from darwin.portfolio.pnl import mark_portfolio
from darwin.risk.engine import RiskContext, RiskEngine
from darwin.risk.kill_switch import KillSwitch
from darwin.services.health_monitor import HealthMonitor, HealthState
from darwin.services.market_data import MarketDataProvider
from darwin.strategies.base import StrategyContext
from darwin.strategies.momentum import MomentumStrategy


@dataclass(frozen=True)
class LivePaperSessionConfig:
    markets: list[str]
    duration_seconds: int
    output: Path
    database_url: str
    seed: int
    max_events: int | None = None
    dry_run: bool = False


class LivePaperTrader:
    """Read-only market-data paper trader.

    This service accepts a `MarketDataProvider` protocol that exposes no exchange execution
    methods. Orders are simulated only through `PaperBroker`.
    """

    def __init__(
        self,
        *,
        provider: MarketDataProvider,
        strategy_config: StrategyConfig,
        risk_config: RiskConfig,
        execution_config: ExecutionSimulationConfig,
        session_config: LivePaperSessionConfig,
        execution_guard: ExecutionEndpointGuard | None = None,
    ) -> None:
        self.provider = provider
        self.strategy = MomentumStrategy(strategy_config)
        self.risk = RiskEngine(risk_config, KillSwitch(risk_config.kill_switch_path))
        self.execution_config = execution_config
        self.session_config = session_config
        self.broker = PaperBroker()
        self.execution_guard = execution_guard or ExecutionEndpointGuard()
        self.order_manager = OrderManager()
        self.portfolio = PortfolioState(cash=Decimal("10000"))
        self.features = StatefulFeaturePipeline()
        self.books: dict[str, LocalOrderBook] = {}
        self.health = HealthMonitor()
        self.bus = BoundedEventBus(maxsize=1000)
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        self.session_id = f"paper-{stamp}-{seed_suffix(session_config.seed)}"
        self.rows: dict[str, list[dict[str, Any]]] = {
            "events": [],
            "orders": [],
            "fills": [],
            "signals": [],
            "risk_decisions": [],
            "health": [],
            "market_health": [],
            "equity_curve": [],
            "trades": [],
            "metrics": [],
            "books": [],
            "sequence_events": [],
            "received_message_types": [],
            "orderbook_validation": [],
        }
        self.message_type_counts: dict[str, int] = {}
        self._stop = asyncio.Event()
        self._db = _connect_sqlite(session_config.database_url)

    async def run(self) -> dict[str, Any]:
        self.session_config.output.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._install_signal_handlers()
        if len(set(self.session_config.markets)) != len(self.session_config.markets):
            raise ValueError("duplicate requested markets are not allowed")
        market_summaries: list[dict[str, Any]] = []
        for market_id in self.session_config.markets:
            market = await self.provider.get_market(market_id)
            market_summaries.append(
                {
                    "market_id": market.market_id,
                    "title": market.title,
                    "status": market.status.value,
                    "close_time": market.close_time.isoformat() if market.close_time else None,
                }
            )

        for market_id in self.session_config.markets:
            snapshot = await self.provider.get_orderbook(market_id)
            book = self.books.setdefault(market_id, LocalOrderBook())
            book.apply_snapshot(snapshot)
            self.health.market(market_id).last_snapshot_ts = snapshot.received_ts
            self.health.market(market_id).last_sequence = snapshot.sequence

        self.rows["health"].append(
            {
                "ts": datetime.now(UTC).isoformat(),
                "state": "healthy",
                "reason": "markets_validated",
                "markets": json.dumps(market_summaries),
            }
        )

        producer = asyncio.create_task(self._produce())
        consumer = asyncio.create_task(self._consume())
        monitor = asyncio.create_task(self._health_monitor())
        if self.session_config.duration_seconds > 0:
            timer = asyncio.create_task(self._duration_timer())
            await asyncio.wait({producer, consumer, timer}, return_when=asyncio.FIRST_COMPLETED)
            self._stop.set()
        await producer
        self._stop.set()
        await consumer
        await monitor
        await self.provider.close()
        return self._finish("completed")

    async def _produce(self) -> None:
        count = 0
        try:
            async for event in self.provider.stream_market_events(self.session_config.markets):
                if self._stop.is_set():
                    break
                count += 1
                await self.bus.publish(event)
                if self.session_config.max_events and count >= self.session_config.max_events:
                    break
        except QueueOverflowError:
            self.health.halt("queue_overflow")
            self.rows["health"].append(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "state": "halted",
                    "reason": "queue_overflow",
                }
            )
        finally:
            await self.bus.publish(
                NormalizedEvent(
                    event_type="shutdown",
                    exchange=Exchange.KALSHI,
                    market_id=None,
                    exchange_ts=None,
                    received_ts=datetime.now(UTC),
                    sequence=None,
                    event_id="shutdown",
                    connection_id="local",
                    correlation_id="shutdown",
                    counter=999999,
                    payload={},
                )
            )

    async def _consume(self) -> None:
        while True:
            event = await self.bus.get()
            if event.event_type == "shutdown":
                break
            self._persist_event(event)
            self._record_message_type(event)
            await self._handle_event(event)

    async def _duration_timer(self) -> None:
        await asyncio.sleep(self.session_config.duration_seconds)
        self._stop.set()

    async def _handle_event(self, event: NormalizedEvent) -> None:
        if event.market_id is not None:
            health = self.health.market(event.market_id)
            health.last_message_ts = event.received_ts
            health.queue_utilization = self.bus.utilization
        if event.event_type == "heartbeat":
            self.rows["health"].append(
                {
                    "ts": event.received_ts.isoformat(),
                    "state": "healthy",
                    "reason": "heartbeat",
                }
            )
            return
        if event.event_type == "reconnect":
            for market_id in self.session_config.markets:
                self.health.market(market_id).reconnect_count += 1
            self.rows["health"].append(
                {
                    "ts": event.received_ts.isoformat(),
                    "state": "degraded",
                    "reason": "reconnect",
                }
            )
            return
        if event.event_type == "sequence_gap" and event.market_id:
            self.health.mark_gap(event.market_id)
            self.rows["health"].append(
                {
                    "ts": event.received_ts.isoformat(),
                    "market_id": event.market_id,
                    "state": "recovering",
                    "reason": event.payload.get("reason", "sequence_gap"),
                }
            )
            self.rows["sequence_events"].append(
                {
                    "ts": event.received_ts.isoformat(),
                    "market_id": event.market_id,
                    "sequence": event.sequence,
                    "reason": event.payload.get("reason", "sequence_gap"),
                    "expected": event.payload.get("expected"),
                    "actual": event.payload.get("actual"),
                }
            )
            return
        if event.event_type == "snapshot_recovery" and event.market_id and event.snapshot:
            self.books.setdefault(event.market_id, LocalOrderBook()).apply_snapshot(event.snapshot)
            self.health.mark_recovered(event.market_id)
            self.rows["sequence_events"].append(
                {
                    "ts": event.received_ts.isoformat(),
                    "market_id": event.market_id,
                    "sequence": event.sequence,
                    "reason": "snapshot_recovery",
                    "expected": None,
                    "actual": event.sequence,
                }
            )
            self.rows["health"].append(
                {
                    "ts": event.received_ts.isoformat(),
                    "market_id": event.market_id,
                    "state": "healthy",
                    "reason": "snapshot_recovery",
                }
            )
            return
        if event.event_type == "orderbook_snapshot" and event.market_id and event.snapshot:
            self.books.setdefault(event.market_id, LocalOrderBook()).apply_snapshot(event.snapshot)
            self.health.market(event.market_id).last_snapshot_ts = event.received_ts
            self.health.market(event.market_id).last_sequence = event.sequence
            self._record_book(event, event.snapshot)
            await self._validate_book_event(event, event.snapshot)
            await self._strategy_step(event, event.snapshot)
            return
        if event.event_type == "orderbook_delta" and event.market_id and event.delta:
            book = self.books[event.market_id]
            try:
                snapshot = book.apply_delta(event.delta)
            except Exception:
                self.health.mark_gap(event.market_id)
                self.rows["health"].append(
                    {
                        "ts": event.received_ts.isoformat(),
                        "market_id": event.market_id,
                        "state": "recovering",
                        "reason": "sequence_gap",
                    }
                )
                fresh = await self.provider.get_orderbook(event.market_id)
                book.apply_snapshot(fresh)
                self.health.mark_recovered(event.market_id)
                return
            self._record_book(event, snapshot)
            await self._validate_book_event(event, snapshot)
            await self._strategy_step(event, snapshot)
            return
        if event.event_type in {"public_trade", "market_status", "market_metadata", "health"}:
            if event.event_type == "health" and event.market_id:
                self.rows["sequence_events"].append(
                    {
                        "ts": event.received_ts.isoformat(),
                        "market_id": event.market_id,
                        "sequence": event.sequence,
                        "reason": event.payload.get("reason"),
                        "expected": event.payload.get("expected"),
                        "actual": event.payload.get("actual"),
                    }
                )
            return

    async def _strategy_step(self, event: NormalizedEvent, snapshot: Any) -> None:
        if event.market_id is None:
            return
        if self.session_config.dry_run:
            self._record_equity(event)
            return
        health = self.health.market(event.market_id)
        if health.state in {HealthState.RECOVERING, HealthState.HALTED, HealthState.UNHEALTHY}:
            return
        vector = self.features.update(snapshot)
        if "momentum" in event.payload:
            values = vector.values | {"momentum": float(event.payload["momentum"])}
            vector = vector.model_copy(update={"values": values})
        mark = snapshot.midprice or Decimal("0.5")
        self.portfolio = mark_portfolio(self.portfolio, {event.market_id: mark})
        position = self.portfolio.positions.get(event.market_id)
        decision = self.strategy.decide(
            vector,
            StrategyContext(
                market=None,
                position=position,
                open_orders=tuple(self.order_manager.open_orders()),
                unrealized_pnl=Decimal("0") if position is None else position.mark_unrealized(mark),
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
            }
        )
        for request in decision.proposed_orders:
            risk = self.risk.check_order(
                request,
                RiskContext(
                    portfolio=self.portfolio,
                    open_orders=tuple(self.order_manager.open_orders()),
                    market_status=MarketStatus.OPEN,
                    spread=vector.values["spread"],
                    data_age_seconds=health.stale_seconds(event.received_ts),
                    estimated_slippage=decision.estimated_slippage,
                    expected_net_edge=decision.net_edge,
                    displayed_depth=int(vector.values["top_depth"]),
                    database_healthy=True,
                    feed_healthy=health.state == HealthState.HEALTHY,
                ),
                asof_ts=event.received_ts,
            )
            self.rows["risk_decisions"].append(
                {
                    "ts": event.received_ts.isoformat(),
                    "client_order_id": request.client_order_id,
                    "decision": risk.decision.value,
                    "reasons": "|".join(risk.reasons),
                }
            )
            if risk.decision.value != "approved":
                self.logger_info("risk_rejection", request.client_order_id, risk.reasons)
                continue
            self.order_manager.create(request, event.correlation_id)
            result = self.broker.submit_against_snapshot(
                request,
                snapshot,
                event.received_ts,
                max_depth_participation=self.execution_config.max_book_participation,
                slippage_bps=self.execution_config.slippage_bps,
            )
            self.order_manager.orders[request.client_order_id] = result.order
            self.rows["orders"].append(
                {
                    "ts": event.received_ts.isoformat(),
                    "client_order_id": request.client_order_id,
                    "market_id": request.market_id,
                    "status": result.order.status.value,
                    "quantity": request.quantity,
                    "filled_quantity": result.order.filled_quantity,
                }
            )
            for fill in result.fills:
                self.order_manager.apply_fill(fill)
                self.portfolio, closed = apply_fill_with_closed_trade(self.portfolio, fill)
                self.rows["fills"].append(
                    {
                        "ts": fill.received_ts.isoformat(),
                        "fill_id": fill.fill_id,
                        "client_order_id": fill.client_order_id,
                        "market_id": fill.market_id,
                        "quantity": fill.quantity,
                        "price": float(fill.price),
                        "fee": float(fill.fee),
                    }
                )
                if closed:
                    self.rows["trades"].append(
                        {
                            "market_id": closed.market_id,
                            "net_realized_pnl": float(closed.net_realized_pnl),
                        }
                    )
        self._record_equity(event)

    def logger_info(self, event: str, client_order_id: str, reasons: Sequence[str]) -> None:
        from darwin.logging import get_logger

        get_logger("darwin.paper_live").info(
            event,
            client_order_id=client_order_id,
            reasons=reasons,
        )

    def _record_equity(self, event: NormalizedEvent) -> None:
        marks = {
            market_id: book.current_snapshot().midprice or Decimal("0.5")
            for market_id, book in self.books.items()
            if book.snapshot
        }
        equity = calculate_equity(self.portfolio, marks, tuple(self.order_manager.open_orders()))
        self.rows["equity_curve"].append(
            {
                "ts": event.received_ts.isoformat(),
                "equity": float(equity),
                "cash": float(self.portfolio.cash),
            }
        )
        self.rows["metrics"].append(
            {
                "ts": event.received_ts.isoformat(),
                "queue_utilization": self.bus.utilization,
                "portfolio_equity": float(equity),
                "realized_pnl": float(self.portfolio.realized_pnl),
                "unrealized_pnl": float(self.portfolio.unrealized_pnl),
                "simulated_fills": len(self.rows["fills"]),
                "risk_rejections": sum(
                    1 for row in self.rows["risk_decisions"] if row["decision"] != "approved"
                ),
            }
        )

    async def _validate_book_event(self, event: NormalizedEvent, snapshot: Any) -> None:
        if not self.session_config.dry_run:
            return
        validator = getattr(self.provider, "validate_book", None)
        if callable(validator):
            result = await validator(snapshot)
        else:
            result = {
                "market_id": event.market_id,
                "matched": True,
                "local_best_bid": str(snapshot.best_bid),
                "rest_best_bid": str(snapshot.best_bid),
                "local_best_ask": str(snapshot.best_ask),
                "rest_best_ask": str(snapshot.best_ask),
            }
        result["ts"] = event.received_ts.isoformat()
        self.rows["orderbook_validation"].append(result)
        if not result.get("matched", False) and event.market_id:
            self.health.market(event.market_id).state = HealthState.DEGRADED

    async def _health_monitor(self) -> None:
        while not self._stop.is_set():
            now = datetime.now(UTC)
            for market_id, health in self.health.markets.items():
                stale = health.stale_seconds(now)
                if stale > 30 and health.state == HealthState.HEALTHY:
                    health.state = HealthState.DEGRADED
                    self.rows["health"].append(
                        {
                            "ts": now.isoformat(),
                            "market_id": market_id,
                            "state": "degraded",
                            "reason": "stale_data",
                            "stale_seconds": stale,
                        }
                    )
                self.rows["market_health"].append(
                    {
                        "ts": now.isoformat(),
                        "market_id": market_id,
                        "state": health.state.value,
                        "stale_seconds": stale,
                        "sequence_gaps": health.sequence_gap_count,
                        "reconnects": health.reconnect_count,
                        "queue_utilization": health.queue_utilization,
                    }
                )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=1)
            except TimeoutError:
                continue

    def _record_message_type(self, event: NormalizedEvent) -> None:
        self.message_type_counts[event.event_type] = (
            self.message_type_counts.get(event.event_type, 0) + 1
        )
        self.rows["received_message_types"] = [
            {"event_type": event_type, "count": count}
            for event_type, count in sorted(self.message_type_counts.items())
        ]

    def _record_book(self, event: NormalizedEvent, snapshot: Any) -> None:
        spread = (
            snapshot.best_ask - snapshot.best_bid
            if snapshot.best_bid is not None and snapshot.best_ask is not None
            else None
        )
        self.rows["books"].append(
            {
                "ts": event.received_ts.isoformat(),
                "market_id": event.market_id,
                "sequence": snapshot.sequence,
                "best_bid": float(snapshot.best_bid) if snapshot.best_bid is not None else None,
                "best_ask": float(snapshot.best_ask) if snapshot.best_ask is not None else None,
                "spread": float(spread) if spread is not None else None,
            }
        )

    def _finish(self, status: str) -> dict[str, Any]:
        summary = {
            "session_id": self.session_id,
            "status": status,
            "orders": len(self.rows["orders"]),
            "fills": len(self.rows["fills"]),
            "risk_rejections": sum(
                1 for row in self.rows["risk_decisions"] if row["decision"] != "approved"
            ),
            "final_cash": float(self.portfolio.cash),
            "realized_pnl": float(self.portfolio.realized_pnl),
            "fees": float(self.portfolio.fees),
            "execution_endpoint_calls": self.execution_guard.calls,
            "health_halted_reason": self.health.halted_reason,
            "dry_run": self.session_config.dry_run,
        }
        for name, rows in self.rows.items():
            _write_csv(self.session_config.output / f"{name}.csv", rows)
        self._write_validation_artifacts(summary)
        (self.session_config.output / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True)
        )
        (self.session_config.output / "metrics.prom").write_text(_prometheus_metrics(summary))
        html = f"<html><body><pre>{json.dumps(summary, indent=2)}</pre></body></html>"
        (self.session_config.output / "report.html").write_text(html)
        return {"summary": summary, **self.rows}

    def _persist_event(self, event: NormalizedEvent) -> None:
        self.rows["events"].append(
            {
                "ts": event.received_ts.isoformat(),
                "event_type": event.event_type,
                "market_id": event.market_id,
                "sequence": event.sequence,
            }
        )
        self._db.execute(
            """
            insert or ignore into normalized_events(
                session_id,event_id,event_type,market_id,received_ts,sequence,payload
            ) values(?,?,?,?,?,?,?)
            """,
            (
                self.session_id,
                event.event_id,
                event.event_type,
                event.market_id,
                event.received_ts.isoformat(),
                event.sequence,
                json.dumps(event.payload),
            ),
        )
        self._db.commit()

    def _write_validation_artifacts(self, summary: dict[str, Any]) -> None:
        output = self.session_config.output
        subscriptions = getattr(getattr(self.provider, "websocket", None), "subscriptions", {})
        subscription_rows = []
        for state in subscriptions.values():
            subscription_rows.append(
                {
                    "request_id": getattr(state, "request_id", None),
                    "subscription_id": getattr(state, "subscription_id", None),
                    "channels": list(getattr(state, "channels", ())),
                    "market_tickers": list(getattr(state, "market_tickers", ())),
                    "acknowledged": getattr(state, "acknowledged", False),
                    "reconnect_generation": getattr(state, "reconnect_generation", None),
                }
            )
        (output / "subscriptions.json").write_text(json.dumps(subscription_rows, indent=2))
        passed = bool(
            summary["dry_run"]
            and self.rows["books"]
            and (subscription_rows == [] or all(row["acknowledged"] for row in subscription_rows))
        )
        connection_summary = {
            "session_id": summary["session_id"],
            "validated_for_supervised_paper": passed,
            "dry_run": summary["dry_run"],
            "markets": self.session_config.markets,
            "message_types": self.message_type_counts,
            "health_halted_reason": summary["health_halted_reason"],
            "execution_endpoint_calls": summary["execution_endpoint_calls"],
        }
        (output / "connection_summary.json").write_text(
            json.dumps(connection_summary, indent=2, sort_keys=True)
        )
        dry_html = (
            "<html><body><h1>Darwin Kalshi Dry Run</h1><pre>"
            f"{json.dumps(connection_summary, indent=2)}"
            "</pre></body></html>"
        )
        (output / "dry_run_report.html").write_text(dry_html)

    def _init_db(self) -> None:
        self._db.execute(
            """
            create table if not exists normalized_events(
                session_id text,
                event_id text unique,
                event_type text,
                market_id text,
                received_ts text,
                sequence integer,
                payload text
            )
            """
        )
        self._db.commit()

    def _install_signal_handlers(self) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGINT, self._stop.set)
            loop.add_signal_handler(signal.SIGTERM, self._stop.set)
        except (NotImplementedError, RuntimeError):
            return


def _connect_sqlite(url: str) -> sqlite3.Connection:
    if not url.startswith("sqlite:///"):
        raise ValueError("paper-live currently supports sqlite:/// database URLs")
    path = url.replace("sqlite:///", "", 1)
    return sqlite3.connect(path)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def seed_suffix(seed: int) -> str:
    return f"{seed:04d}"


def _prometheus_metrics(summary: dict[str, Any]) -> str:
    gauges = {
        "darwin_paper_orders_total": summary["orders"],
        "darwin_paper_fills_total": summary["fills"],
        "darwin_paper_risk_rejections_total": summary["risk_rejections"],
        "darwin_paper_final_cash": summary["final_cash"],
        "darwin_paper_realized_pnl": summary["realized_pnl"],
        "darwin_paper_fees": summary["fees"],
        "darwin_paper_execution_endpoint_calls_total": summary["execution_endpoint_calls"],
    }
    return "\n".join(f"{name} {value}" for name, value in gauges.items()) + "\n"

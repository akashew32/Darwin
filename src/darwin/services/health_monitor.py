from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class HealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"
    HALTED = "halted"


@dataclass
class MarketHealth:
    state: HealthState = HealthState.HEALTHY
    last_message_ts: datetime | None = None
    last_snapshot_ts: datetime | None = None
    last_sequence: int | None = None
    sequence_gap_count: int = 0
    reconnect_count: int = 0
    snapshot_recovery_count: int = 0
    malformed_message_count: int = 0
    queue_utilization: float = 0.0

    def stale_seconds(self, now: datetime | None = None) -> float:
        if self.last_message_ts is None:
            return float("inf")
        current = now or datetime.now(UTC)
        return (current - self.last_message_ts).total_seconds()


@dataclass
class HealthMonitor:
    markets: dict[str, MarketHealth] = field(default_factory=dict)
    database_healthy: bool = True
    halted_reason: str | None = None

    def market(self, market_id: str) -> MarketHealth:
        return self.markets.setdefault(market_id, MarketHealth())

    def mark_gap(self, market_id: str) -> None:
        health = self.market(market_id)
        health.sequence_gap_count += 1
        health.state = HealthState.RECOVERING

    def mark_recovered(self, market_id: str) -> None:
        health = self.market(market_id)
        health.snapshot_recovery_count += 1
        health.state = HealthState.HEALTHY

    def halt(self, reason: str) -> None:
        self.halted_reason = reason
        for health in self.markets.values():
            health.state = HealthState.HALTED

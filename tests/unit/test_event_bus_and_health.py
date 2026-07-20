from datetime import UTC, datetime

import pytest

from darwin.data.event_bus import BoundedEventBus, QueueOverflowError
from darwin.data.events import NormalizedEvent
from darwin.domain.enums import Exchange
from darwin.services.health_monitor import HealthMonitor, HealthState


def event(counter: int) -> NormalizedEvent:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return NormalizedEvent(
        event_type="heartbeat",
        exchange=Exchange.KALSHI,
        market_id=None,
        exchange_ts=None,
        received_ts=now,
        sequence=None,
        event_id=f"e-{counter}",
        connection_id="c",
        correlation_id="corr",
        counter=counter,
        payload={},
    )


@pytest.mark.asyncio
async def test_event_bus_uses_bounded_queue() -> None:
    bus = BoundedEventBus(maxsize=1)
    await bus.publish(event(1))
    with pytest.raises(QueueOverflowError):
        await bus.publish(event(2))
    assert bus.halted


@pytest.mark.parametrize(
    "action,state",
    [
        ("gap", HealthState.RECOVERING),
        ("recover", HealthState.HEALTHY),
        ("halt", HealthState.HALTED),
    ],
)
def test_health_state_transitions(action: str, state: HealthState) -> None:
    monitor = HealthMonitor()
    if action == "gap":
        monitor.mark_gap("M")
    elif action == "recover":
        monitor.mark_gap("M")
        monitor.mark_recovered("M")
    else:
        monitor.market("M")
        monitor.halt("x")
    assert monitor.market("M").state == state


def test_event_sort_key_uses_sequence_before_counter() -> None:
    first = event(2)
    second = event(1)
    assert second.sort_key < first.sort_key

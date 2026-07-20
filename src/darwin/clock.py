from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Injectable clock for deterministic services and tests."""

    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value.astimezone(UTC)

    def now(self) -> datetime:
        return self.value

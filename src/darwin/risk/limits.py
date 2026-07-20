from dataclasses import dataclass


@dataclass(frozen=True)
class LimitUsage:
    name: str
    used: float
    limit: float

    @property
    def breached(self) -> bool:
        return self.used > self.limit

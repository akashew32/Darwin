from dataclasses import dataclass


@dataclass
class ExecutionEndpointGuard:
    """Instrumented guard proving paper paths did not reach exchange execution."""

    calls: int = 0

    def record_forbidden_call(self, endpoint: str) -> None:
        self.calls += 1
        raise AssertionError(f"paper trading must not call exchange endpoint: {endpoint}")

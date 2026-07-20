from datetime import datetime
from hashlib import blake2b


class ClientOrderIdFactory:
    """Deterministic collision-resistant client order IDs for replayable simulations."""

    def __init__(self, strategy_id: str) -> None:
        self.strategy_id = strategy_id
        self.sequence = 0

    def next(self, market_id: str, ts: datetime, action: str) -> str:
        self.sequence += 1
        raw = f"{self.strategy_id}|{market_id}|{ts.isoformat()}|{action}|{self.sequence}"
        digest = blake2b(raw.encode(), digest_size=6).hexdigest()
        return f"dw-{self.strategy_id}-{market_id}-{self.sequence:06d}-{digest}"[:64]

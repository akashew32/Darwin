from datetime import datetime
from typing import Any, Protocol


class Repository(Protocol):
    async def insert_raw_message(
        self,
        exchange: str,
        event_type: str,
        payload: dict[str, Any],
        received_ts: datetime,
    ) -> None: ...

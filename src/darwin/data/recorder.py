from datetime import datetime
from typing import Any

from darwin.data.repository import Repository


class DataRecorder:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    async def record_raw(
        self, exchange: str, event_type: str, payload: dict[str, Any], received_ts: datetime
    ) -> None:
        await self.repository.insert_raw_message(exchange, event_type, payload, received_ts)

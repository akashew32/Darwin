import asyncio
from dataclasses import dataclass

from darwin.data.events import NormalizedEvent


@dataclass
class BoundedEventBus:
    maxsize: int = 1000

    def __post_init__(self) -> None:
        self.queue: asyncio.Queue[NormalizedEvent] = asyncio.Queue(maxsize=self.maxsize)
        self.overflow_count = 0
        self.halted = False

    async def publish(self, event: NormalizedEvent) -> None:
        if self.queue.full():
            self.overflow_count += 1
            self.halted = True
            raise QueueOverflowError("normalized event queue overflow")
        await self.queue.put(event)

    async def get(self) -> NormalizedEvent:
        return await self.queue.get()

    @property
    def utilization(self) -> float:
        return self.queue.qsize() / self.maxsize


class QueueOverflowError(RuntimeError):
    pass

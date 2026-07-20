import asyncio
import time


class AsyncTokenBucket:
    def __init__(self, rate_per_second: float, capacity: int) -> None:
        self.rate = rate_per_second
        self.capacity = capacity
        self.tokens = float(capacity)
        self.updated = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self.lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
            self.updated = now
            if self.tokens < 1:
                await asyncio.sleep((1 - self.tokens) / self.rate)
                self.tokens = 0
                self.updated = time.monotonic()
            self.tokens -= 1

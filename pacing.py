import asyncio, time

class Pacer:
    def __init__(self, min_gap=7.0, burst=4):
        self.gap = min_gap
        self.burst = burst
        self.tokens = burst
        self.last = time.monotonic()
        self.lock = asyncio.Lock()

    async def wait(self):
        async with self.lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.burst, self.tokens + (now - self.last) / self.gap)
                self.last = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                await asyncio.sleep((1 - self.tokens) * self.gap)
import asyncio
import config

class Budget:
    def __init__(self, store):
        self.store = store
        self.lock = asyncio.Lock()
        self.res = {"h": 0, "d": 0}

    def reset(self):
        self.res = {"h": 0, "d": 0}

    async def take(self, n=1, backoff=1.0):
        async with self.lock:
            c = config.load()["budget"]
            h = self.store.count("action", 3600) + self.res["h"]
            d = self.store.count("action", 86400) + self.res["d"]
            if h + n > c["actions_per_hour"] * backoff:
                return False
            if d + n > c["actions_per_day"]:
                return False
            self.res["h"] += n
            self.res["d"] += n
            return True

    async def commit(self, n=1):
        async with self.lock:
            self.res["h"] = max(0, self.res["h"] - n)
            self.res["d"] = max(0, self.res["d"] - n)
            self.store.add_actions(n)
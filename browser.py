import asyncio, os, random
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import config

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

STEALTH_JS = """
Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
window.chrome={runtime:{}};
Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
"""

def _proxy():
    url = os.getenv("PROXY_URL")
    return {"server": url} if url else None

async def pause(lo=None, hi=None):
    c = config.load()["budget"]
    lo = lo or c["pause_min_ms"]
    hi = hi or c["pause_max_ms"]
    await asyncio.sleep(random.uniform(lo, hi) / 1000)

class Session:
    def __init__(self, profile=None):
        self.profile = profile or config.load()["profile_dir"]
        self._pw = None
        self.ctx = None
        self.page = None

    async def __aenter__(self):
        self._pw = await async_playwright().start()
        self.ctx = await self._pw.chromium.launch_persistent_context(
            self.profile,
            headless=os.getenv("HEADLESS", "0") == "1",
            channel="chromium",
            user_agent=UA,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id=os.getenv("TZ_ID", "America/New_York"),
            proxy=_proxy(),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        await self.ctx.add_init_script(STEALTH_JS)
        self.page = self.ctx.pages[0] if self.ctx.pages else await self.ctx.new_page()
        await Stealth().apply_stealth_async(self.page)
        return self

    async def __aexit__(self, *a):
        try:
            if self.ctx:
                await self.ctx.close()
        finally:
            if self._pw:
                await self._pw.stop()

    async def goto(self, url, wait="domcontentloaded"):
        await self.page.goto(url, wait_until=wait, timeout=45000)
        await pause(900, 2200)

    async def logged_in(self):
        import health
        sig = await health.probe(self)
        if sig:
            print("  !! session blocked: %s (url=%s)" % (sig, self.page.url))
            return False
        url = self.page.url
        return "/login" not in url and "i/flow/login" not in url

    async def type_like_human(self, text):
        for ch in text:
            await self.page.keyboard.type(ch)
            await asyncio.sleep(random.uniform(0.012, 0.075))
            if ch == " " and random.random() < 0.06:
                await asyncio.sleep(random.uniform(0.25, 0.7))

    async def scroll_jitter(self, n=1):
        for _ in range(n):
            await self.page.mouse.wheel(0, random.randint(380, 900))
            await pause(700, 2100)

async def login(profile=None):
    async with Session(profile) as s:
        await s.goto("https://x.com/login")
        print("Log in by hand, then press Enter here.")
        input()

if __name__ == "__main__":
    asyncio.run(login(os.getenv("PROFILE")))

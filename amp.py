import os
from browser import Session, pause

PROFILE = "./chrome-amp"

async def amplify(tid, text):
    if os.getenv("AMP") != "1":
        return
    async with Session(PROFILE) as s:
        if not await s.logged_in():
            return
        await s.goto("https://x.com/i/status/" + tid)
        await pause(1800, 3200)
        try:
            await s.page.locator('[data-testid="like"]').first.click()
            await pause(1200, 2600)
        except Exception:
            pass
        await pause(20000, 70000)
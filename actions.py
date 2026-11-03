import asyncio, os, re, datetime
from browser import pause
import config

DRY = lambda: os.getenv("DRY_RUN") == "1"
SKEW = 300
BASELINE = {"ids": set()}

async def _articles(s):
    out = []
    arts = await s.page.locator('article[data-testid="tweet"]').all()
    for a in arts:
        try:
            if await a.locator('[data-testid="socialContext"]').count():
                ctx = (await a.locator('[data-testid="socialContext"]').inner_text()).lower()
                if "pinned" in ctx:
                    continue
            link = await a.locator('a[href*="/status/"]').first.get_attribute("href")
            tid = re.search(r"/status/(\d+)", link).group(1)
            dt = await a.locator("time").first.get_attribute("datetime")
            out.append((tid, dt))
        except Exception:
            continue
    return out

async def prime_baseline(s):
    await s.goto("https://x.com/home")
    BASELINE["ids"] = {tid for tid, _ in await _articles(s)}

async def _capture_new_id(s, handle, replies=False):
    if DRY():
        return None
    url = ("https://x.com/" + handle + "/with_replies") if replies else "https://x.com/home"
    for attempt in range(3):
        try:
            await s.goto(url)
            for tid, dt in await _articles(s):
                if tid in BASELINE["ids"]:
                    continue
                try:
                    when = datetime.datetime.fromisoformat(dt.replace("Z", "+00:00"))
                except Exception:
                    continue
                age = (datetime.datetime.now(datetime.UTC) - when).total_seconds()
                if age <= SKEW:
                    return tid
        except Exception:
            pass
        await asyncio.sleep(2.5 * (attempt + 1))
    print("  !! id capture failed")
    return None

async def _send(s, text):
    box = s.page.locator('[data-testid="tweetTextarea_0"]').first
    await box.click()
    await pause(400, 900)
    await s.type_like_human(text)
    await pause(700, 1600)
    if DRY():
        print("  [DRY] " + text)
        await s.page.keyboard.press("Escape")
        return True
    await s.page.keyboard.press("Control+Enter")
    await pause(2000, 3400)
    return True

async def post(s, text, handle):
    if DRY():
        print("  [DRY] post: " + text)
        return {"dry_run": True, "text": text}
    await s.goto("https://x.com/compose/post")
    await pause(1200, 2000)
    if not await _send(s, text):
        return None
    tid = await _capture_new_id(s, handle)
    if tid:
        BASELINE["ids"].add(tid)
    return {"id": tid} if tid else None

async def post_with_media(s, text, path, handle, alt=""):
    if DRY():
        print("  [DRY] post with media: " + text)
        return {"dry_run": True, "text": text}
    await s.goto("https://x.com/compose/post")
    await pause(1200, 2000)
    await s.page.locator('input[type="file"]').first.set_input_files(path)
    await pause(2500, 4500)
    if alt:
        try:
            await s.page.locator('[aria-label*="ALT"]').first.click()
            await pause(500, 900)
            await s.page.keyboard.type(alt)
            await s.page.get_by_text("Done", exact=False).first.click()
        except Exception:
            pass
    await pause(800, 1500)
    if not await _send(s, text):
        return None
    tid = await _capture_new_id(s, handle)
    if tid:
        BASELINE["ids"].add(tid)
    return {"id": tid} if tid else None

async def reply(s, tid, text, handle):
    if DRY():
        print("  [DRY] reply to %s: %s" % (tid, text))
        return {"dry_run": True, "text": text}
    await s.goto("https://x.com/i/status/" + tid)
    await s.page.locator('[data-testid="reply"]').first.click()
    await pause(1200, 2400)
    if not await _send(s, text):
        return None
    new = await _capture_new_id(s, handle, replies=True)
    if new:
        BASELINE["ids"].add(new)
    return {"id": new} if new else None

async def quote(s, tid, text, handle):
    if DRY():
        print("  [DRY] quote %s: %s" % (tid, text))
        return {"dry_run": True, "text": text}
    await s.goto("https://x.com/i/status/" + tid)
    await pause(1400, 2300)
    await s.page.locator('[data-testid="retweet"]').first.click()
    await pause(700, 1300)
    await s.page.get_by_text("Quote", exact=False).first.click()
    await pause(1300, 2400)
    if not await _send(s, text):
        return None
    new = await _capture_new_id(s, handle)
    if new:
        BASELINE["ids"].add(new)
    return {"id": new} if new else None

async def pin(s, tid):
    if DRY():
        print("  [DRY] pin: " + tid)
        return False
    await s.goto("https://x.com/i/status/" + tid)
    await pause(1400, 2400)
    try:
        await s.page.locator('[data-testid="caret"]').first.click()
        await pause(600, 1100)
        await s.page.get_by_text("Pin", exact=False).first.click()
        await pause(900, 1600)
    except Exception as e:
        print("  !! pin: %s" % e)

async def follow(s, handle):
    if DRY():
        print("  [DRY] follow @" + handle)
        return False
    await s.goto("https://x.com/" + handle)
    btn = s.page.locator('[data-testid$="-follow"]').first
    if not await btn.count():
        return False
    await btn.click()
    await pause(900, 1800)
    return True

async def unfollow(s, handle):
    if DRY():
        print("  [DRY] unfollow @" + handle)
        return False
    await s.goto("https://x.com/" + handle)
    btn = s.page.locator('[data-testid$="-unfollow"]').first
    if not await btn.count():
        return False
    await btn.click()
    await pause(500, 1000)
    try:
        await s.page.get_by_test_id("confirmationSheetConfirm").click(timeout=4000)
    except Exception:
        pass
    await pause(900, 1700)
    return True

async def follows_you(s, handle):
    await s.goto("https://x.com/" + handle)
    await pause(1200, 2000)
    return await s.page.get_by_text("Follows you", exact=False).count() > 0
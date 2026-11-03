import random
import actions, config
from browser import pause

async def ratio_ok(store):
    fol = int(store.kv("followers") or 0)
    fwing = store.q1("SELECT COUNT(*) FROM follows WHERE unfollowed=0")[0]
    if not fol:
        return True
    return fwing / fol <= config.load()["follows"]["max_total_ratio"]

async def run(s, store):
    c = config.load()["follows"]
    if not c["enabled"]:
        return
    if store.count("follow", 86400) >= c["max_per_day"]:
        return
    src = random.choice(c["sources"])
    await s.goto("https://x.com/" + src + "/followers")
    await pause(2000, 3500)
    await s.scroll_jitter(random.randint(2, 5))

    cells = await s.page.locator('[data-testid="UserCell"]').all()
    picked = 0
    for h in cells:
        if picked >= random.randint(6, 12):
            break
        try:
            link = await h.locator('a[href^="/"]').first.get_attribute("href")
            handle = link.strip("/").split("/")[0]
        except Exception:
            continue
        if not handle or store.seen_follow(handle):
            continue
        if await actions.follow(s, handle):
            store.mark_follow(handle)
            picked += 1
            await pause(3000, 9000)

async def unfollow_pass(s, store):
    if not await ratio_ok(store):
        print("  (ratio ceiling, skipping unfollows)")
        return
    for handle in store.unfollow_due(config.load()["follows"]["unfollow_after_days"]):
        if handle.lower() in [w.lower() for w in config.load()["follows"]["whitelist"]]:
            continue
        if await actions.follows_you(s, handle):
            store.mark_mutual(handle)
            continue
        if await actions.unfollow(s, handle):
            store.mark_unfollowed(handle)
            await pause(4000, 11000)
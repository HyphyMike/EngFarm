import pathlib, time

SELECTORS = {
    "tweet": ['article[data-testid="tweet"]', 'article[role="article"]', '[role="article"]'],
    "trend": ['[data-testid="trend"]', '[data-testid="trendItem"]', 'div[aria-label*="Trend"]'],
    "tweet_text": ['[data-testid="tweetText"]', 'div[lang]'],
    "reply_btn": ['[data-testid="reply"]', 'div[aria-label="Reply"]'],
    "editor": ['[data-testid="tweetTextarea_0"]', 'div[role="textbox"]'],
    "like": ['[data-testid="like"]', '[data-testid="unlike"]'],
    "follow": ['[data-testid$="-follow"]'],
    "unfollow": ['[data-testid$="-unfollow"]'],
    "confirm": ['[data-testid="confirmationSheetConfirm"]'],
    "usercell": ['[data-testid="UserCell"]', 'div[data-testid="cellInnerDiv"]'],
    "analytics": ['[aria-label*="View post analytics"]'],
    "bookmark": ['[data-testid="bookmark"]'],
    "notification": ['[data-testid="notification"]', 'article[role="article"]'],
}

QUARANTINE_AFTER = 2

async def pick(store, page, name):
    if store.kv("quarantine:" + name):
        return None
    for sel in SELECTORS[name]:
        loc = page.locator(sel)
        if await loc.count():
            store.bump_sel(name, True)
            return loc
    store.bump_sel(name, False)
    if store.sel_failures(name) >= QUARANTINE_AFTER:
        store.set_kv("quarantine:" + name, "1")
        print("  !! %s quarantined" % name)
    await dump(page, name)
    return None

def release_quarantine(store):
    for (k,) in store.q("SELECT k FROM kv WHERE k LIKE 'quarantine:%'"):
        store.del_kv(k)

async def dump(page, name):
    d = pathlib.Path("dom")
    d.mkdir(exist_ok=True)
    (d / ("%s-%d.html" % (name, int(time.time())))).write_text(await page.content())

async def healthy(page):
    body = await page.content()
    if "arkose" in body or "captcha" in body.lower():
        return "captcha"
    if "Something went wrong" in body:
        return "error_toast"
    if "Rate limit exceeded" in body:
        return "ratelimit"
    return None

async def deindexed(anon_page, handle, tid):
    from browser import pause
    await anon_page.goto("https://x.com/search?q=from%3A" + handle + "&f=live")
    await pause(2000, 3500)
    return tid not in (await anon_page.content())
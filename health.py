import pathlib, time
import killswitch

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
    "notification": ['[data-testid="notification"]', 'article[data-testid="tweet"]',
                     'article[role="article"]'],
}

QUARANTINE_AFTER = 2

COOLDOWN = {"http403": 3600, "ratelimit": 1800, "captcha": 1200,
            "empty": 900, "neterr": 300, "error_toast": 600, "login": 21600}

async def probe(page, status=None, last_url=None):
    """Classify an already-loaded page; never retries a blocked request."""
    if last_url is not None and page.url != last_url:
        status = None  # recorded status belongs to a previous navigation
    if status == 403:
        return "http403"
    if status == 429:
        return "ratelimit"
    html = await page.content()
    lower = html.lower()
    if "arkose" in lower or "captcha" in lower:
        return "captcha"
    if "rate limit exceeded" in lower:
        return "ratelimit"
    if "something went wrong" in lower:
        return "error_toast"
    try:
        body = await page.locator("body").inner_text(timeout=5000)
    except Exception:
        body = ""
    if len(body.strip()) < 40:
        return "empty"
    return None

def set_cooldown(store, signature):
    seconds = COOLDOWN.get(signature)
    if not seconds:
        return
    store.set_kv("cooldown_until", str(time.time() + seconds))
    store.set_kv("cooldown_reason", signature)
    if signature == "login":
        # logged out needs a human, not a nap
        killswitch.trip("logged out")

async def pick(store, page, name):
    if store.kv("quarantine:" + name):
        return None
    for sel in SELECTORS[name]:
        loc = page.locator(sel)
        if await loc.count():
            store.bump_sel(name, True)
            return loc
    try:
        body_text = await page.locator("body").inner_text(timeout=3000)
    except Exception:
        body_text = ""
    if not body_text.strip():
        await dump(page, name)
        print("  !! %s page is blank; selector check skipped (url=%s title=%s)" %
              (name, page.url, await page.title()))
        return None

    store.bump_sel(name, False)
    if store.sel_failures(name) >= QUARANTINE_AFTER:
        store.set_kv("quarantine:" + name, "1")
        print("  !! %s quarantined" % name)
    await dump(page, name)
    return None

def reset_selector_quarantine(store, name):
    store.del_kv("quarantine:" + name)
    store.w("UPDATE sel_stats SET fail=0 WHERE name=?", (name,))

def release_quarantine(store):
    for (k,) in store.q("SELECT k FROM kv WHERE k LIKE 'quarantine:%'"):
        store.del_kv(k)

async def dump(page, name):
    d = pathlib.Path("dom")
    d.mkdir(exist_ok=True)
    html = await page.content()
    metadata = "<!-- url=%s title=%s -->\n" % (page.url, await page.title())
    (d / ("%s-%d.html" % (name, int(time.time())))).write_text(metadata + html)

async def healthy(page, status=None, last_url=None):
    return await probe(page, status, last_url)

async def deindexed(anon_page, handle, tid):
    from browser import pause
    await anon_page.goto("https://x.com/search?q=from%3A" + handle + "&f=live")
    await pause(2000, 3500)
    return tid not in (await anon_page.content())

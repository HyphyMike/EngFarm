import json, pathlib, re, time, urllib.parse
from html.parser import HTMLParser
from browser import pause
import config

def parse_count(s):
    s = (s or "").strip().replace(",", "")
    m = re.match(r"([\d.]+)\s*([KMB])", s, re.I)
    if m:
        mult = {"k": 1e3, "m": 1e6, "b": 1e9}[m.group(2).lower()]
        return int(float(m.group(1)) * mult)
    d = re.sub(r"\D", "", s)
    return int(d) if d else 0

class _Counter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hits = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("data-testid") in ("trend", "tweet", "tweetText") or a.get("role") == "article":
            self.hits += 1

def count_selectors(html):
    p = _Counter()
    p.feed(html)
    return p.hits

def capture(tweets):
    d = pathlib.Path("candidates")
    d.mkdir(exist_ok=True)
    p = d / (time.strftime("%Y-%m-%d") + ".json")
    existing = json.loads(p.read_text()) if p.exists() else []
    seen = {c["id"] for c in existing}
    existing += [t for t in tweets if t["id"] not in seen]
    p.write_text(json.dumps(existing[-400:]))

async def parse_tweets(s, limit=25):
    out = []
    arts = await s.page.locator('article[data-testid="tweet"]').all()
    for a in arts[:limit]:
        try:
            txt = await a.locator('[data-testid="tweetText"]').inner_text()
            link = await a.locator('a[href*="/status/"]').first.get_attribute("href")
            tid = re.search(r"/status/(\d+)", link).group(1)
            handle = re.search(r"^/([^/]+)/status", link).group(1)
            dt = await a.locator("time").first.get_attribute("datetime")
            likes = replies = 0
            if await a.locator('[data-testid="like"]').count():
                likes = parse_count(await a.locator('[data-testid="like"]').inner_text())
            if await a.locator('[data-testid="reply"]').count():
                replies = parse_count(await a.locator('[data-testid="reply"]').inner_text())
            out.append({"id": tid, "handle": handle, "text": txt,
                        "datetime": dt, "likes": likes, "replies": replies})
        except Exception:
            continue
    return out

async def scrape_trends(s):
    await s.goto("https://x.com/explore/tabs/trending")
    await pause(1800, 3400)
    out = []
    nodes = await s.page.locator('[data-testid="trend"]').all()
    for n in nodes[:25]:
        try:
            txt = await n.inner_text()
        except Exception:
            continue
        lines = [l.strip() for l in txt.split("\n") if l.strip()]
        name, vol = None, 0
        for l in lines:
            if re.match(r"^#?\w", l) and not l.lower().startswith(("trending", "posts")):
                name = name or l
            if "post" in l.lower():
                vol = parse_count(l)
        if name and vol >= config.load()["trends"]["min_post_volume"]:
            out.append({"name": name, "volume": vol})
    return out

async def scrape_search(s, query, limit=25):
    await s.goto("https://x.com/search?q=" + urllib.parse.quote(query) + "&f=live")
    await pause(2200, 4000)
    await s.scroll_jitter(2)
    return await parse_tweets(s, limit)

async def scrape_own_metrics(s, tid):
    await s.goto("https://x.com/i/status/" + tid)
    await pause(1600, 2600)
    m = {"views": 0, "likes": 0, "replies": 0, "reposts": 0, "bookmarks": 0}
    try:
        bar = s.page.locator('[aria-label*="View post analytics"]').first
        m["views"] = parse_count(await bar.inner_text())
    except Exception:
        pass
    for key, sel in (("likes", '[data-testid="like"], [data-testid="unlike"]'),
                     ("replies", '[data-testid="reply"]'),
                     ("reposts", '[data-testid="retweet"], [data-testid="unretweet"]'),
                     ("bookmarks", '[data-testid="bookmark"]')):
        try:
            loc = s.page.locator(sel).first
            if await loc.count():
                m[key] = parse_count(await loc.inner_text())
        except Exception:
            pass
    return m

async def scrape_profile(s, handle, limit=10, followers=False):
    await s.goto("https://x.com/" + handle)
    await pause(1600, 2800)
    if followers:
        html = await s.page.content()
        m = re.search(r'([\d.,KMB]+)\s*Followers', html)
        return parse_count(m.group(1)) if m else 0
    await s.scroll_jitter(1)
    return [t["id"] for t in await parse_tweets(s, limit)]

async def scrape_profile_tweets(s, handle, limit=20):
    await s.goto("https://x.com/" + handle + "/with_replies")
    await pause(1800, 3000)
    return await parse_tweets(s, limit)
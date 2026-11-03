"""Official X API v2 access. Reads (optional) for discovery, writes only for drafts you approved."""
import os, re, time, logging, urllib.parse
from datetime import datetime, timezone, timedelta
import httpx

log = logging.getLogger("engfarm.x")
DRY = os.environ.get("DRY_RUN", "1") == "1"

def tweet_id_from(s):
    m = re.search(r"/status(?:es)?/(\d+)", s) or re.fullmatch(r"\s*(\d{5,})\s*", s)
    return m.group(1) if m else None

def lookup_public(url_or_id):
    """Fetch one tweet's text/author via X's public oEmbed endpoint (no API key needed)."""
    tid = tweet_id_from(url_or_id)
    if not tid:
        raise ValueError("Couldn't find a tweet id in that link")
    url = f"https://x.com/i/status/{tid}"
    r = httpx.get("https://publish.twitter.com/oembed",
                  params={"url": url, "omit_script": "1"}, timeout=20)
    r.raise_for_status()
    j = r.json()
    html = j.get("html", "")
    text = re.sub(r"<[^>]+>", "", (re.search(r"<p[^>]*>(.*?)</p>", html, re.S) or [None, ""])[1])
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'"))
    author = j.get("author_url", "").rstrip("/").rsplit("/", 1)[-1]
    return {"id": tid, "author": author, "text": text.strip(),
            "url": f"https://x.com/{author}/status/{tid}"}

def intent_url(text, in_reply_to=None):
    q = {"text": text}
    if in_reply_to:
        q["in_reply_to"] = in_reply_to
    return "https://x.com/intent/post?" + urllib.parse.urlencode(q)


class X:
    def __init__(self):
        self._w = self._r = None

    def _writer(self):
        if self._w is None:
            import tweepy
            self._w = tweepy.Client(
                consumer_key=os.environ["X_API_KEY"], consumer_secret=os.environ["X_API_SECRET"],
                access_token=os.environ["X_ACCESS_TOKEN"],
                access_token_secret=os.environ["X_ACCESS_SECRET"],
                wait_on_rate_limit=True)
        return self._w

    def _reader(self):
        if self._r is None:
            import tweepy
            tok = os.environ.get("X_BEARER_TOKEN")
            if not tok:
                raise RuntimeError("Set X_BEARER_TOKEN in .env to use Find tweets "
                                   "(or paste tweet links instead).")
            self._r = tweepy.Client(bearer_token=tok, wait_on_rate_limit=True)
        return self._r

    def search(self, discovery):
        """Recent tweets from watched accounts / keywords, filtered by age and likes."""
        queries = [f"from:{a} -is:retweet -is:reply" for a in discovery.get("accounts", [])]
        queries += [f'"{k}" -is:retweet -is:reply lang:en' for k in discovery.get("keywords", [])]
        since = datetime.now(timezone.utc) - timedelta(minutes=discovery.get("max_age_minutes", 120))
        out = []
        for q in queries:
            try:
                resp = self._reader().search_recent_tweets(
                    query=q, max_results=max(10, min(100, discovery.get("per_query", 10))),
                    start_time=since, tweet_fields=["created_at", "public_metrics", "author_id"],
                    expansions=["author_id"], user_fields=["username"])
            except Exception as e:
                log.warning("search failed for %r: %s", q, e)
                continue
            users = {u.id: u.username for u in (resp.includes or {}).get("users", [])}
            for t in resp.data or []:
                likes = t.public_metrics.get("like_count", 0)
                if likes < discovery.get("min_likes", 0):
                    continue
                author = users.get(t.author_id, "i")
                out.append({"id": str(t.id), "author": author, "text": t.text, "likes": likes,
                            "created_at": t.created_at.isoformat() if t.created_at else "",
                            "url": f"https://x.com/{author}/status/{t.id}"})
        return out

    def post(self, text, reply_to=None, quote_id=None):
        if DRY:
            log.info("[DRY_RUN] would post %r reply_to=%s quote=%s", text, reply_to, quote_id)
            return f"dry-{int(time.time())}"
        r = self._writer().create_tweet(text=text, in_reply_to_tweet_id=reply_to,
                                        quote_tweet_id=quote_id)
        return str(r.data["id"])

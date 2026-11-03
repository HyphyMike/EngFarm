import hashlib
import feedparser

FEEDS = ["https://hnrss.org/frontpage",
         "https://feeds.arstechnica.com/arstechnica/technology-lab",
         "http://export.arxiv.org/rss/cs.AI"]

async def pull(store):
    for url in FEEDS:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:12]:
                h = hashlib.sha1(e.link.encode()).hexdigest()[:16]
                if store.kv("feed:" + h):
                    continue
                store.set_kv("feed:" + h, e.title)
                store.add_seed(e.title, url)
        except Exception as ex:
            print("  !! feed %s: %s" % (url, ex))
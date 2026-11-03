import random
import semantic
from scrape import scrape_search

NICHE = ["AI agents", "LLM tooling", "startup growth"]

async def mine(s, store):
    q = random.choice(NICHE)
    tweets = await scrape_search(s, q, 30)
    for t in tweets:
        if t["handle"].lower() == "yourhandle":
            continue
        store.see_peer(t["handle"], t["likes"], t["replies"])
    for t in tweets[:20]:
        try:
            store.save_peer_post(t["handle"], t["text"], await semantic.embed(t["text"]))
        except Exception:
            pass
    ranked = store.peer_leaders(10)
    print("[PEERS] %s" % ranked)
    return ranked
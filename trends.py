import asyncio, datetime, random
import actions, config, llm, semantic
from scrape import scrape_search, scrape_trends
from store import Store

def _age_min(dt):
    try:
        d = datetime.datetime.fromisoformat(dt.replace("Z", "+00:00"))
        return (datetime.datetime.now(datetime.UTC) - d).total_seconds() / 60
    except Exception:
        return None

async def run(s, store):
    if not config.load()["trends"]["enabled"]:
        return
    found = await scrape_trends(s)
    if not found:
        return
    found = [t for t in found if not store.seen_trend(found and t["name"], 6 * 3600)]
    random.shuffle(found)
    found = found[:3]

    for t in found:
        store.mark_trend(t["name"])
        print("[TREND] %s (%d posts)" % (t["name"], t["volume"]))

        take = await llm.trend_take(t["name"], store.recent_texts(6))
        if take and not store.seen_text(take):
            handle = config.load()["account_handle"]
            result = await actions.post(s, take, handle)
            if result and result.get("id"):
                store.add_post(take, "trend_take", tid=result["id"], trend=t["name"])

        cands = await scrape_search(s, t["name"], 20)
        cands = [c for c in cands if c["handle"].lower() != config.load()["account_handle"].lower()
                 and not store.seen_tweet(c["id"])]

        def ok(c):
            age = _age_min(c["datetime"])
            return (age is not None and age <= 10 and c["likes"] >= 2
                    and (c["replies"] / max(c["likes"], 1)) <= 0.35)

        cands = [c for c in cands if ok(c)]
        cands.sort(key=lambda c: -c["likes"])

        for c in cands[:2]:
            txt = await llm.reply_to(c["text"], c["handle"], trend=t["name"])
            if not txt or store.seen_text(txt):
                continue
            print("  [TREND REPLY] @%s: %s" % (c["handle"], txt))
            result = await actions.reply(s, c["id"], txt, config.load()["account_handle"])
            if result and result.get("id"):
                store.add_reply(result["id"], "trend_reply", trend=t["name"])
            await asyncio.sleep(random.uniform(45, 130))
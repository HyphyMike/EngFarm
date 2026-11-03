import asyncio, random
import actions, health, llm, scoring, stance

MAX_DEPTH = 2

async def run(s, store):
    await s.goto("https://x.com/notifications/mentions")
    await asyncio.sleep(2.5)
    if not await health.pick(store, s.page, "notification"):
        return
    from scrape import parse_tweets
    mentions = await parse_tweets(s, 25)
    mentions.sort(key=lambda m: -store.rel(m["handle"]))

    for m in mentions:
        if store.seen_tweet(m["id"]):
            continue
        depth = store.thread_depth(m["id"])
        if depth >= MAX_DEPTH:
            continue
        if not (store.is_own_thread(m["id"]) or await llm.is_answerable(m["text"])):
            continue
        if await scoring.incoming(m) < 55:
            continue

        st = stance.advance(store, m["id"])
        txt = await llm.thread_followup(m["text"], store.thread_context(m["id"]), stance.directive(st))
        if await llm.is_dead_end(txt):
            store.close_thread(m["id"])
            continue

        print("  [CONVO d%d %s] @%s: %s" % (depth, st, m["handle"], txt))
        result = await actions.reply(s, m["id"], txt, __import__("config").load()["account_handle"])
        if result and result.get("id"):
            store.add_reply(result["id"], "conversation")
            store.bump_depth(m["id"])
            store.bump_relationship(m["handle"], 1.0)
        await asyncio.sleep(random.uniform(40, 150))
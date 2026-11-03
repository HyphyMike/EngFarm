import llm

async def day_ok(store):
    trends = store.q("SELECT name, vol FROM trends ORDER BY ts DESC LIMIT 10")
    verdict = await llm.assess_day(trends, store.metrics_digest())
    if verdict.startswith("SKIP"):
        print("  (skip day: %s)" % verdict)
        store.set_kv("skip_day", verdict)
        return False
    store.del_kv("skip_day")
    return True
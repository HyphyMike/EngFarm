import asyncio, datetime, os, random
import actions, analytics, audience, bandit, claims, config
import conversation, digest, follow, gates, health, llm, memory, outbox
import peers, planner, semantic, style, threads, topics, trends

if os.getenv("BLUESKY") == "1":
    import bluesky

def now():
    return datetime.datetime.now()

async def plan(store):
    if not await gates.day_ok(store):
        return
    await planner.build(store)

async def trends_job(s, store):
    await trends.run(s, store)

async def post_job(s, store):
    c = config.load()
    if store.count("post", 86400) >= c["posting"]["max_per_day"]:
        return
    if now().hour in range(1, 7):
        return

    q = store.next_send()
    if q:
        h, text, fmt = q
        if await emit(s, store, text, fmt):
            store.drop_send(h)
        return

    p = store.today_plan()
    if not p or not p["posts"]:
        return
    item = p["posts"].pop(0)
    store.save_plan(p)
    if await semantic.too_similar(store, item["angle"], 0.80):
        txt = await llm.hot_take(item["angle"])
    else:
        txt = await llm.from_angle(item["fmt"], item["angle"],
                                   memory.lessons_block(store), p.get("segment", ""))
    await emit(s, store, txt, item["fmt"], arm=item["fmt"])

async def thread_job(s, store):
    if now().hour in range(2, 7):
        return
    c = config.load()
    chain = await threads.build_chain(random.choice(c["trends"]["seeds"]), 4)
    if await threads.hook_score(chain[0]) < 65:
        return print("  (weak hook)")
    root = await threads.publish(s, store, chain)
    if root:
        store.add_post(chain[0], "thread", tid=root)

async def chain_repair_job(s, store):
    await threads.repair(s, store)

async def conversation_job(s, store):
    await conversation.run(s, store)

async def follows_job(s, store):
    await follow.run(s, store)

async def misc_job(s, store):
    await peers.mine(s, store)

async def reconcile_job(s, store):
    await outbox.reconcile(store, s, config.load()["account_handle"])

async def emit(s, store, text, fmt, trend=None, arm=None):
    verdict, out = await claims.gate(store, text)
    if verdict == "queue":
        return False
    out = await style.conform(store, out, text)
    if store.seen_text(out):
        return False
    if await semantic.too_similar(store, out):
        print("  (self-dup)")
        return False
    if await semantic.echoes_peers(store, out):
        print("  (peer-echo)")
        return False
    if await topics.hot(store, out):
        print("  (topic cooldown)")
        return False

    if os.getenv("DRY_RUN") == "1":
        print("  [DRY] preview/%s: %s" % (fmt, out))
        return True

    oid = outbox.intend(store, out, fmt, trend)
    handle = config.load()["account_handle"]
    try:
        res = await actions.post(s, out, handle)
    except Exception as e:
        outbox.failed(store, oid, type(e).__name__)
        raise

    tid = res and res.get("id")
    outbox.sent(store, oid, tid)
    if tid:
        store.add_post(out, fmt, tid=tid, trend=trend)
        await semantic.remember(store, tid, out)
        await topics.claim(store, out)
        if arm:
            bandit.update(store, arm, "tech", now().hour, 0.0)
        if os.getenv("BLUESKY") == "1":
            await bluesky.mirror(out)
        print("  [SENT/%s] %s" % (fmt, out))
        return True
    print("  (sent, id unverified - queued for reconciliation)")
    return True
import asyncio, os, random, time, traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

import actions, analytics, audience, budget, claims, config, digest
import health, ingest, jobs, killswitch, memory, pacing, resources, store as _store

load_dotenv()
STORE = _store.Store()
BUD = budget.Budget(STORE)
PACER = pacing.Pacer()
BACKOFF = {"mult": 1.0}
LANES = asyncio.Semaphore(3)
ERR = {"TimeoutError": "slow", "TargetClosedError": "crash",
       "Error": "dom", "TooManyRequests": "throttle"}

def cooling():
    until = float(STORE.kv("cooldown_until") or 0)
    left = until - time.time()
    if left > 0:
        print("  (X access cooldown: %s, %d min left)" %
              (STORE.kv("cooldown_reason") or "blocked", int(left // 60)))
        return True
    return False

async def guard(s, store):
    if killswitch.engaged() or cooling():
        return False
    sig = await health.healthy(s.page, getattr(s, "last_status", None))
    if sig:
        BACKOFF["mult"] = min(BACKOFF["mult"] * 1.8, 8)
        health.set_cooldown(store, sig)
        print("  !! %s; cooling down" % sig)
        return False
    BACKOFF["mult"] = max(BACKOFF["mult"] * 0.9, 1.0)
    return True

async def run_job(name, fn, s, store, lane_name):
    import job_costs, journal
    if store.kv("jobq:" + name):
        return
    cost = job_costs.estimate(store, name)
    if not await BUD.take(cost, BACKOFF["mult"]):
        return
    await PACER.wait()
    journal.mark(store, lane_name, name, "start")
    before = store.count("action", 3600)
    try:
        await fn(s, store)
        STORE.clear_failures(name)
        journal.mark(store, lane_name, name, "ok")
    except Exception as e:
        k = ERR.get(type(e).__name__, "other")
        STORE.bump_failure(name, k)
        journal.mark(store, lane_name, name, "fail:" + k)
        print("  !! %s [%s] %s" % (name, k, e))
        if STORE.consec_failures(name) >= 4:
            STORE.set_kv("jobq:" + name, "1")
            print("  !! %s quarantined" % name)
    finally:
        job_costs.observe(store, name, max(1, store.count("action", 3600) - before))
        await BUD.commit(cost)

async def lane(name, jobs_list, prime=True):
    from browser import Session
    async with LANES:
        try:
            if cooling():
                return
            async with Session() as s:
                if not await s.logged_in():
                    if getattr(s, "block_signal", None):
                        health.set_cooldown(STORE, s.block_signal)
                    print("  !! %s: blocked or logged out" % name)
                    return
                if prime:
                    await actions.prime_baseline(s)
                for jname, fn in jobs_list:
                    if not await guard(s, STORE):
                        break
                    await run_job(jname, fn, s, STORE, name)
                    await asyncio.sleep(random.uniform(25, 95))
        except Exception as e:
            print("  !! lane %s: %s: %s" % (name, type(e).__name__, e))
            traceback.print_exc()

async def cycle():
    import journal
    BUD.reset()
    journal.cycle(STORE)
    global LANES
    LANES = asyncio.Semaphore(resources.lanes())
    lanes = [
        ("content", [("trends", jobs.trends_job), ("post", jobs.post_job)], True),
        ("conversation", [("conversation", jobs.conversation_job)], True),
        ("threads", [("chain_repair", jobs.chain_repair_job), ("thread", jobs.thread_job)], True),
        ("reconcile", [("reconcile", jobs.reconcile_job)], False),
    ]
    if random.random() < 0.5:
        lanes.append(("tail", [("misc", jobs.misc_job), ("follows", jobs.follows_job)], False))
    await asyncio.gather(*(lane(n, j, p) for n, j, p in lanes), return_exceptions=True)

async def cycle_analytics():
    from browser import Session
    if cooling():
        return
    async with LANES:
        async with Session() as s:
            if not await s.logged_in():
                if getattr(s, "block_signal", None):
                    health.set_cooldown(STORE, s.block_signal)
                return
            await analytics.collect(s, STORE, 25)
            analytics.retune(STORE)
            await analytics.refresh_followers(s, STORE)
    await memory.reflect(STORE)
    await audience.recluster(STORE)
    await claims.approve_queue(STORE)
    await claims.expire_pass(STORE)
    digest.write(STORE, BACKOFF["mult"], killswitch.engaged())

async def cycle_health():
    from playwright.async_api import async_playwright
    from browser import Session
    if cooling():
        return
    async with Session() as s:
        if not await s.logged_in():
            if getattr(s, "block_signal", None):
                health.set_cooldown(STORE, s.block_signal)
            return
        last = STORE.q1("SELECT tid FROM posted WHERE tid IS NOT NULL ORDER BY ts DESC LIMIT 1")
        if not last:
            return
    pw = await async_playwright().start()
    ctx = await (await pw.chromium.launch(headless=True)).new_context()
    if await health.deindexed(await ctx.new_page(), config.load()["account_handle"], last[0]):
        print("!! DEINDEXED")
        killswitch.trip("deindexed")
    await pw.stop()

async def nightly():
    STORE.snapshot()
    memory.prune(STORE)
    health.release_quarantine(STORE)
    for (k,) in STORE.q("SELECT k FROM kv WHERE k LIKE 'jobq:%'"):
        STORE.del_kv(k)
    await ingest.pull(STORE)
    print("[NIGHTLY] done")

def reset_backoff():
    if BACKOFF["mult"] > 1.0:
        print("  (backoff reset %.1f->1.0)" % BACKOFF["mult"])
    BACKOFF["mult"] = 1.0

async def main():
    import llm
    llm.bind(STORE)
    health.reset_selector_quarantine(STORE, "notification")
    STORE.snapshot()
    print("startup planning")
    await jobs.plan(STORE)
    print("startup cycle")
    await cycle()
    if config.load().get("analytics", {}).get("run_on_startup", False):
        print("startup analytics")
        await cycle_analytics()

    sched = AsyncIOScheduler()
    sched.add_job(cycle, "interval", minutes=22)
    sched.add_job(cycle_analytics, "interval", hours=6, jitter=900)
    sched.add_job(cycle_health, "interval", hours=2, jitter=600)
    sched.add_job(reset_backoff, "interval", minutes=45)
    sched.add_job(nightly, "cron", hour=4, minute=20)
    sched.start()
    print("up | dry=%s | lanes<=%d | PAUSE=kills" % (os.getenv("DRY_RUN"), resources.lanes()))
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
import datetime, random
import audience, bandit, llm

MULT = {0: 1.0, 1: 1.0, 2: 1.0, 3: 0.9, 4: 0.8, 5: 0.5, 6: 0.4}

async def build(store):
    wd = datetime.date.today().weekday()
    target = max(1, round(5 * MULT[wd]))
    digest = store.metrics_digest()
    hour = datetime.datetime.now().hour
    arms = ["bait_question", "hot_take", "quote_tweet", "trend_reply"]
    cluster = random.randint(0, 5)
    seg = audience.label(store, cluster)

    plan = {"date": datetime.date.today().isoformat(), "posts": [], "replies": [],
            "experiment": None, "target": target, "segment": seg}

    for _ in range(target):
        fmt = bandit.choose(store, arms, "tech", hour)
        angle = await llm.plan_post(fmt, digest, store.recent_lessons(15), seg)
        plan["posts"].append({"fmt": fmt, "angle": angle})

    plan["replies"] = await llm.plan_replies(digest, store.top_targets(15))
    plan["experiment"] = await llm.propose_experiment(store.recent_lessons(20), [])
    store.save_plan(plan)
    print("[PLAN wd=%d] %d posts for segment '%s'" % (wd, target, seg))
    return plan
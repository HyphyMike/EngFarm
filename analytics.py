import datetime, json, math
import yaml
import bandit, config
from scrape import scrape_own_metrics, scrape_profile

def reward(m):
    return (m["views"] * 0.02 + m["likes"] + m["replies"] * 2.5
            + m["bookmarks"] * 3.0 + m["reposts"] * 2.0)

async def collect(s, store, limit=25):
    for tid, fmt in store.unsettled_metrics(limit):
        if store.metric_fresh(tid, 3600):
            continue
        m = await scrape_own_metrics(s, tid)
        store.save_metrics(tid, fmt, m)
        bandit.update(store, fmt, "tech", datetime.datetime.now().hour, reward(m))
        store.settle(tid)

def retune(store):
    stats = {}
    for fmt, js in store.q("SELECT fmt, json FROM metrics WHERE settled=1"):
        stats.setdefault(fmt, []).append(reward(json.loads(js)))
    stats = {k: v for k, v in stats.items() if len(v) >= 2}
    if len(stats) < 2:
        return
    means = {f: sum(v) / len(v) for f, v in stats.items()}
    mx = max(means.values()) or 1
    exps = {f: math.exp((means[f] / mx) / 1.0) for f in means}
    tot = sum(exps.values())
    new = {f: max(8.0, 100 * exps[f] / tot) for f in exps}
    n = sum(new.values())
    new = {f: round(v * 100 / n, 1) for f, v in new.items()}
    raw = yaml.safe_load(open("config.yaml"))
    raw["posting"]["mix"] = new
    yaml.safe_dump(raw, open("config.yaml", "w"), sort_keys=False)
    print("[TUNE] %s" % new)

async def refresh_followers(s, store):
    n = await scrape_profile(s, config.load()["account_handle"], 0, followers=True)
    if n:
        store.set_kv("followers", n)
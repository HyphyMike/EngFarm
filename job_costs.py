BASE = {"trends": 14, "post": 9, "conversation": 11, "thread": 18,
        "chain_repair": 7, "misc": 12, "follows": 16, "analytics": 22}

def estimate(store, job):
    r = store.q1("SELECT avg FROM job_cost WHERE job=?", (job,))
    return r[0] if r else BASE.get(job, 8)

def observe(store, job, actual):
    cur = estimate(store, job)
    store.w("INSERT INTO job_cost VALUES (?,?) ON CONFLICT(job) DO UPDATE "
            "SET avg=avg*0.8+?*0.2", (job, cur, actual))
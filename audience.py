import time
import numpy as np
import semantic

K = 6

async def recluster(store):
    handles = store.engaged_handles(300)
    if len(handles) < 30:
        return
    vecs, keep = [], []
    for h in handles:
        bio = store.handle_bio(h)
        if not bio:
            continue
        vecs.append(await semantic.embed(bio))
        keep.append(h)
    if len(vecs) < K:
        return
    X = np.stack(vecs)
    C = X[np.random.choice(len(X), K, replace=False)]
    for _ in range(12):
        lab = np.argmin(((X[:, None] - C[None]) ** 2).sum(-1), axis=1)
        for k in range(K):
            if (lab == k).any():
                C[k] = X[lab == k].mean(0)
    for h, l in zip(keep, lab):
        store.set_cluster(h, int(l), store.handle_bio(h) or "")
    store.set_kv("clusters_ts", str(time.time()))
    print("[AUDIENCE] clustered %d handles into %d" % (len(keep), K))

def label(store, cluster):
    hs = store.cluster_members(cluster, 8)
    return ", ".join(hs) or "unknown"
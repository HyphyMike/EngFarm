import re, secrets, time
import semantic

def intend(store, text, fmt, trend=None):
    oid = secrets.token_hex(8)
    store.w("INSERT INTO outbox VALUES (?,?,?,'intended',NULL,?,NULL,?)",
            (oid, text, fmt, time.time(), trend))
    return oid

def sent(store, oid, tid=None):
    store.w("UPDATE outbox SET state=?, tid=? WHERE id=?",
            ("confirmed" if tid else "sent", tid, oid))
    if tid:
        store.w("UPDATE outbox SET confirmed=? WHERE id=?", (time.time(), oid))

def failed(store, oid, why=""):
    store.w("UPDATE outbox SET state='failed' WHERE id=?", (oid,))
    print("  !! outbox failed %s %s" % (oid, why))

def unconfirmed(store, older_than=120):
    return store.q("SELECT id,text,fmt,trend,ts FROM outbox "
                   "WHERE state IN ('intended','sent') AND ts<?",
                   (time.time() - older_than,))

def norm(t):
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()

async def reconcile(store, s, handle):
    from scrape import scrape_profile_tweets
    found = await scrape_profile_tweets(s, handle, 20)
    if not found:
        return 0
    pool = {norm(t["text"])[:60]: t for t in found}
    fixed = 0
    for oid, text, fmt, trend, ts in unconfirmed(store):
        key = norm(text)[:60]
        hit = pool.get(key)
        if not hit:
            cands = [(len(set(key.split()) & set(k.split())), t) for k, t in pool.items()]
            best = max(cands, default=(0, None))
            if best[0] < 4:
                continue
            hit = best[1]
        store.w("UPDATE outbox SET state='reconciled', tid=?, confirmed=? WHERE id=?",
                (hit["id"], time.time(), oid))
        if not store.seen_text(text):
            store.add_post(text, fmt, tid=hit["id"], trend=trend)
            await semantic.remember(store, hit["id"], text)
        fixed += 1
        print("  [RECONCILED] " + text[:60] + " -> " + hit["id"])
    return fixed
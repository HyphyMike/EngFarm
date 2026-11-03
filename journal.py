import secrets, time

def cycle(store):
    cid = secrets.token_hex(6)
    store.set_kv("cycle", cid)
    return cid

def mark(store, lane, job, state):
    store.w("INSERT INTO journal VALUES (?,?,?,?,?)",
            (store.kv("cycle"), lane, job, state, time.time()))

def in_flight(store, max_age=1800):
    return store.q("SELECT cycle,lane,job FROM journal WHERE state='start' AND ts>?",
                   (time.time() - max_age,))
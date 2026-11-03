TRANSITIONS = {
    "asserted": lambda n: "challenged" if n else "asserted",
    "challenged": lambda n: "defended" if n < 2 else "conceded",
    "defended": lambda n: "conceded",
    "conceded": lambda n: "closed",
    "closed": lambda n: "closed",
}

def state(store, tid):
    return store.stance(tid) or "asserted"

def advance(store, tid, challenged=True):
    if challenged:
        store.bump_challenge(tid)
    nxt = TRANSITIONS[state(store, tid)](store.challenges(tid))
    store.set_stance(tid, nxt)
    return nxt

def directive(st):
    return {
        "asserted": "Extend your point with one concrete detail.",
        "challenged": "Engage the specific objection. Concede the sub-point if it's fair.",
        "defended": "Hold the core claim but narrow it. One sentence of steelman, then your line.",
        "conceded": "Concede cleanly. Keep the part you still believe. No restating.",
        "closed": "One short closing line.",
    }[st]
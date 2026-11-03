import datetime, pathlib

def write(store, backoff=1.0, paused=False):
    d = pathlib.Path("digests")
    d.mkdir(exist_ok=True)
    p = d / (datetime.date.today().isoformat() + ".md")
    lines = ["# " + datetime.date.today().isoformat(), "", "## System",
             "- paused: " + str(paused),
             "- backoff: %.1fx" % backoff,
             "- pending claims: %d" % store.pending_claims(),
             "- quarantined: " + str(store.quarantined() or "none"),
             "- tokens/follower: " + str(store.cost_per_follower()),
             "- skip_day: " + str(store.kv("skip_day") or "no"), "", "## By format"]
    for fmt, v, l, rp, bk in store.metrics_digest():
        lines.append("- %s: %s views, %s likes, %s replies, %s saves" % (fmt, v, l, rp, bk))
    lines += ["", "## Lessons"] + ["- " + x for x in store.recent_lessons(5)]
    p.write_text("\n".join(lines))
    print("[DIGEST] " + str(p))
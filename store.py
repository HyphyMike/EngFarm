import sqlite3, threading, time, hashlib, re, json, shutil, pathlib
import numpy as np

SCHEMA = open("schema.sql").read()

class Store:
    def __init__(self, path="engfarm.db"):
        self.path = path
        self._lock = threading.RLock()
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.execute("PRAGMA journal_mode=WAL")
        self.c.execute("PRAGMA busy_timeout=5000")
        self.c.execute("PRAGMA synchronous=NORMAL")
        with self._lock:
            self.c.executescript(SCHEMA)
            cols = {r[1] for r in self.c.execute("PRAGMA table_info(peer_posts)")}
            if "text_len" not in cols:
                self.c.execute("ALTER TABLE peer_posts ADD COLUMN text_len INT")
            self.c.commit()

    def w(self, sql, args=()):
        with self._lock:
            self.c.execute(sql, args)
            self.c.commit()

    def q(self, sql, args=()):
        with self._lock:
            return self.c.execute(sql, args).fetchall()

    def q1(self, sql, args=()):
        with self._lock:
            return self.c.execute(sql, args).fetchone()

    @staticmethod
    def norm(t):
        return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()

    def _h(self, t):
        return hashlib.sha1(self.norm(t).encode()).hexdigest()[:16]

    def kv(self, k):
        r = self.q1("SELECT v FROM kv WHERE k=?", (k,))
        return r and r[0]

    def set_kv(self, k, v):
        self.w("INSERT OR REPLACE INTO kv VALUES (?,?)", (k, str(v)))

    def del_kv(self, k):
        self.w("DELETE FROM kv WHERE k=?", (k,))

    def seen_text(self, t):
        return bool(self.q1("SELECT 1 FROM posted WHERE hash=?", (self._h(t),)))

    def seen_tweet(self, i):
        return bool(self.q1("SELECT 1 FROM replied WHERE tweet_id=?", (i,)))

    def add_post(self, text, fmt, tid=None, trend=None):
        self.w("INSERT OR IGNORE INTO posted VALUES (?,?,?,?,?,?)",
               (self._h(text), text, fmt, tid, trend, time.time()))
        self._ev("post")

    def add_reply(self, tid, kind="reply", trend=None):
        self.w("INSERT OR IGNORE INTO replied VALUES (?,?,?,?)",
               (tid, kind, trend, time.time()))
        self._ev("reply")

    def _ev(self, kind):
        for t in ("acts", "stat_events"):
            self.w("INSERT INTO %s VALUES (?,?)" % t, (kind, time.time()))

    def add_actions(self, n=1):
        with self._lock:
            for _ in range(n):
                self.c.execute("INSERT INTO acts VALUES (?,?)", ("action", time.time()))
            self.c.commit()

    def count(self, kind, w):
        return self.q1("SELECT COUNT(*) FROM acts WHERE kind=? AND ts>?",
                       (kind, time.time() - w))[0]

    def recent_posts(self, n):
        return self.q("SELECT text, fmt, tid FROM posted ORDER BY ts DESC LIMIT ?", (n,))

    def recent_texts(self, n):
        return [t for (t,) in self.q("SELECT text FROM posted ORDER BY ts DESC LIMIT ?", (n,))]

    def newest_ids(self, n=20):
        return [x for (x,) in self.q(
            "SELECT tid FROM posted WHERE tid IS NOT NULL ORDER BY ts DESC LIMIT ?", (n,))]

    def best_post(self, days):
        r = self.q1("SELECT p.tid FROM posted p JOIN metrics m ON m.tid=p.tid "
                    "WHERE p.ts>? ORDER BY json_extract(m.json,'$.views') DESC LIMIT 1",
                    (time.time() - days * 86400,))
        return r and r[0]

    def day_performance(self):
        return self.q("SELECT p.text, json_extract(m.json,'$.views') v FROM posted p "
                      "JOIN metrics m ON m.tid=p.tid WHERE p.ts>? ORDER BY v DESC",
                      (time.time() - 86400,))

    def save_vector(self, key, b):
        self.w("INSERT OR REPLACE INTO vectors VALUES (?,?,?)", (key, b, time.time()))

    def recent_vectors(self, n):
        return [np.frombuffer(v, dtype=np.float32)
                for (v,) in self.q("SELECT vec FROM vectors ORDER BY ts DESC LIMIT ?", (n,))]

    def save_peer_post(self, h, text, vec):
        self.w("INSERT OR REPLACE INTO peer_posts (hash, handle, vec, ts, text_len) "
               "VALUES (?,?,?,?,?)",
               (self._h(text), h, vec.tobytes(), time.time(), len(text)))

    def recent_peer_vectors(self, n):
        return [(length or 0, np.frombuffer(v, dtype=np.float32)) for length, v in
                self.q("SELECT text_len, vec FROM peer_posts ORDER BY ts DESC LIMIT ?", (n,))]

    def add_cooldown(self, key, vec):
        self.w("INSERT OR REPLACE INTO cooldowns VALUES (?,?,?)",
               (key, vec.tobytes(), time.time()))

    def live_cooldowns(self, window):
        return [np.frombuffer(v, dtype=np.float32)
                for (v,) in self.q("SELECT vec FROM cooldowns WHERE ts>?",
                                   (time.time() - window,))]

    def stance(self, tid):
        r = self.q1("SELECT state FROM stances WHERE tid=?", (tid,))
        return r and r[0]

    def set_stance(self, tid, st):
        self.w("INSERT INTO stances VALUES (?,?,?,0) ON CONFLICT(tid) DO UPDATE SET state=?",
               (tid, st, time.time(), st))

    def challenges(self, tid):
        r = self.q1("SELECT challenges FROM stances WHERE tid=?", (tid,))
        return r[0] if r else 0

    def bump_challenge(self, tid):
        self.w("INSERT INTO stances VALUES (?,?,?,1) ON CONFLICT(tid) DO UPDATE "
               "SET challenges=challenges+1", (tid, "asserted", time.time()))

    def thread_depth(self, i):
        r = self.q1("SELECT depth FROM threads WHERE id=?", (i,))
        return r[0] if r else 0

    def bump_depth(self, i):
        self.w("INSERT INTO threads VALUES (?,1,0,?) ON CONFLICT(id) DO UPDATE SET depth=depth+1",
               (i, time.time()))

    def close_thread(self, i):
        self.w("INSERT INTO threads VALUES (?,0,1,?) ON CONFLICT(id) DO UPDATE SET closed=1",
               (i, time.time()))

    def is_own_thread(self, i):
        return bool(self.q1("SELECT 1 FROM posted WHERE tid=?", (i,))) or self.thread_depth(i) > 0

    def thread_context(self, i):
        r = self.q1("SELECT text FROM posted WHERE tid=?", (i,))
        return r[0] if r else ""

    def save_chain(self, root, beats):
        self.w("INSERT OR REPLACE INTO chains VALUES (?,?,?,0,?)",
               (root, json.dumps(beats), 1, time.time()))

    def advance_chain(self, root):
        self.w("UPDATE chains SET cursor=cursor+1 WHERE root=?", (root,))

    def finish_chain(self, root):
        self.w("UPDATE chains SET done=1 WHERE root=?", (root,))

    def open_chains(self, age=6 * 3600):
        return self.q("SELECT root,beats,cursor FROM chains WHERE done=0 AND ts>?",
                      (time.time() - age,))

    def add_lesson(self, t):
        self.w("INSERT INTO lessons VALUES (?,?,1.0,0)", (time.time(), t))

    def recent_lessons(self, n):
        rows = self.q("SELECT ts,text,weight,hits FROM lessons ORDER BY ts DESC LIMIT 200")
        scored = sorted(((r[2] * (0.94 ** ((time.time() - r[0]) / 86400)) + r[3] * 0.1, r[1])
                         for r in rows), reverse=True)
        return [t for _, t in scored[:n]]

    def hit_lesson(self, t):
        self.w("UPDATE lessons SET hits=hits+1 WHERE text=?", (t,))

    def bandit_state(self, arm, dim):
        r = self.q1("SELECT A,b FROM bandit WHERE arm=?", (arm,))
        if not r:
            return np.eye(dim), np.zeros(dim)
        return np.frombuffer(r[0]).reshape(dim, dim), np.frombuffer(r[1])

    def save_bandit(self, arm, A, b):
        self.w("INSERT OR REPLACE INTO bandit VALUES (?,?,?)",
               (arm, A.tobytes(), b.tobytes()))

    def add_claim(self, text, reason, ttl_h=6, slot=0):
        self.w("INSERT INTO claims (text,reason,expires,slot,ts) VALUES (?,?,?,?,?)",
               (text, reason, time.time() + ttl_h * 3600, slot, time.time()))

    def expired_claims(self):
        return self.q("SELECT id,text FROM claims WHERE status='pending' AND expires<?",
                      (time.time(),))

    def pending_claims(self):
        return self.q1("SELECT COUNT(*) FROM claims WHERE status='pending'")[0]

    def approve_claim(self, cid):
        r = self.q1("SELECT text FROM claims WHERE id=?", (cid,))
        self.w("UPDATE claims SET status='approved' WHERE id=?", (cid,))
        return r and r[0]

    def approved_claims(self):
        return self.q("SELECT id,text FROM claims WHERE status='approved'")

    def retire_claim(self, cid, status="sent"):
        self.w("UPDATE claims SET status=? WHERE id=?", (status, cid))

    def save_plan(self, p):
        self.w("INSERT OR REPLACE INTO plans VALUES (?,?)", (p["date"], json.dumps(p)))

    def today_plan(self):
        import datetime
        r = self.q1("SELECT json FROM plans WHERE date=?",
                    (datetime.date.today().isoformat(),))
        return json.loads(r[0]) if r else None

    def save_metrics(self, tid, fmt, m):
        self.w("INSERT OR REPLACE INTO metrics VALUES (?,?,?,?,0)",
               (tid, fmt, json.dumps(m), time.time()))

    def unsettled_metrics(self, n=25):
        return self.q("SELECT tid, fmt FROM metrics WHERE settled=0 LIMIT ?", (n,))

    def settle(self, tid):
        self.w("UPDATE metrics SET settled=1 WHERE tid=?", (tid,))

    def metrics_digest(self):
        return self.q("SELECT fmt, AVG(json_extract(json,'$.views')), "
                      "AVG(json_extract(json,'$.likes')), AVG(json_extract(json,'$.replies')), "
                      "AVG(json_extract(json,'$.bookmarks')) FROM metrics GROUP BY fmt")

    def set_cluster(self, h, c, bio=""):
        self.w("INSERT OR REPLACE INTO audience VALUES (?,?,?)", (h, c, bio))

    def engaged_handles(self, n):
        return [x for (x,) in self.q(
            "SELECT DISTINCT handle FROM audience ORDER BY rowid DESC LIMIT ?", (n,))]

    def handle_bio(self, h):
        r = self.q1("SELECT bio FROM audience WHERE handle=?", (h,))
        return r and r[0]

    def cluster_members(self, c, n):
        return [x for (x,) in self.q("SELECT handle FROM audience WHERE cluster=? LIMIT ?", (c, n))]

    def bump_relationship(self, h, d=1.0):
        self.w("INSERT INTO relationships VALUES (?,?,?) ON CONFLICT(handle) DO UPDATE "
               "SET score=score+?, ts=?", (h, d, time.time(), d, time.time()))

    def rel(self, h):
        r = self.q1("SELECT score FROM relationships WHERE handle=?", (h,))
        return r[0] if r else 0

    def top_targets(self, n):
        return [x for (x,) in self.q(
            "SELECT handle FROM relationships ORDER BY score DESC LIMIT ?", (n,))]

    def see_peer(self, h, l, r):
        self.w("INSERT OR REPLACE INTO peers VALUES (?,?,?,?)", (h, l, r, time.time()))

    def peer_leaders(self, n):
        return [x for (x,) in self.q(
            "SELECT handle FROM peers WHERE replies>0 "
            "ORDER BY CAST(likes AS REAL)/replies DESC LIMIT ?", (n,))]

    def bump_sel(self, name, ok):
        col = "ok" if ok else "fail"
        self.w("INSERT INTO sel_stats VALUES (?,0,0) ON CONFLICT(name) DO NOTHING", (name,))
        self.w("UPDATE sel_stats SET %s=%s+1 WHERE name=?" % (col, col), (name,))

    def sel_failures(self, name):
        r = self.q1("SELECT fail FROM sel_stats WHERE name=?", (name,))
        return r[0] if r else 0

    def quarantined(self):
        return [k.split(":")[1] for (k,) in self.q("SELECT k FROM kv WHERE k LIKE 'quarantine:%'")]

    def bump_failure(self, job, kind):
        self.w("INSERT INTO failures VALUES (?,?,?,1)", (job, kind, time.time()))

    def consec_failures(self, job):
        rows = self.q("SELECT job FROM failures ORDER BY rowid DESC LIMIT 12")
        n = 0
        for (j,) in rows:
            if j != job:
                break
            n += 1
        return n

    def clear_failures(self, job):
        self.w("DELETE FROM failures WHERE job=?", (job,))

    def add_cost(self, kind, tokens):
        if tokens:
            self.w("INSERT INTO costs VALUES (?,?,?)", (kind, tokens, time.time()))

    def cost_per_follower(self):
        tok = self.q1("SELECT COALESCE(SUM(tokens),0) FROM costs")[0]
        fol = int(self.kv("followers") or 0)
        return round(tok / fol, 1) if fol else None

    def add_seed(self, title, source=""):
        self.w("INSERT OR IGNORE INTO seeds VALUES (?,?,?,0)", (self._h(title), title, source))

    def fresh_seeds(self, n):
        return [t for (t,) in self.q(
            "SELECT title FROM seeds WHERE used=0 ORDER BY rowid LIMIT ?", (n,))]

    def use_seed(self, title):
        self.w("UPDATE seeds SET used=1 WHERE title=?", (title,))

    def queue_send(self, text, fmt="claim"):
        self.w("INSERT OR REPLACE INTO pending_send VALUES (?,?,?,?,0)",
               (self._h(text), text, fmt, time.time()))

    def next_send(self):
        r = self.q1("SELECT hash,text,fmt FROM pending_send WHERE claimed=0 ORDER BY ts LIMIT 1")
        if r:
            self.w("UPDATE pending_send SET claimed=1 WHERE hash=?", (r[0],))
        return r

    def drop_send(self, h):
        self.w("DELETE FROM pending_send WHERE hash=?", (h,))

    def snapshot(self, keep=7):
        d = pathlib.Path("snapshots")
        d.mkdir(exist_ok=True)
        with self._lock:
            self.c.commit()
            shutil.copy(self.path, d / ("state-%d.db" % int(time.time())))
        for old in sorted(d.glob("state-*.db"), key=lambda p: p.stat().st_mtime)[:-keep]:
            old.unlink()

    def prune(self, vectors, metrics_days, events_days):
        now = time.time()
        self.w("DELETE FROM vectors WHERE tid NOT IN "
               "(SELECT tid FROM vectors ORDER BY ts DESC LIMIT ?)", (vectors,))
        self.w("DELETE FROM peer_posts WHERE ts<?", (now - 30 * 86400,))
        self.w("DELETE FROM metrics WHERE ts<?", (now - metrics_days * 86400,))
        self.w("DELETE FROM stat_events WHERE ts<?", (now - events_days * 86400,))
        self.w("DELETE FROM acts WHERE ts<?", (now - 30 * 86400,))
        self.w("DELETE FROM claims WHERE status='pending' AND expires<?", (now - 86400,))
        self.w("DELETE FROM failures WHERE ts<?", (now - 7 * 86400,))
    def seen_trend(self, n, window):
        r = self.q1("SELECT ts FROM trends WHERE name=?", (n,))
        return bool(r and time.time() - r[0] < window)

    def mark_trend(self, n):
        self.w("INSERT OR REPLACE INTO trends VALUES (?,?,0,0)", (n, time.time()))

    def seen_follow(self, h):
        return bool(self.q1("SELECT 1 FROM follows WHERE handle=?", (h,)))

    def mark_follow(self, h):
        self.w("INSERT OR IGNORE INTO follows VALUES (?,?,0,0)", (h, time.time()))

    def mark_mutual(self, h):
        self.w("UPDATE follows SET mutual=1 WHERE handle=?", (h,))

    def mark_unfollowed(self, h):
        self.w("UPDATE follows SET unfollowed=1 WHERE handle=?", (h,))

    def unfollow_due(self, days):
        cut = time.time() - days * 86400
        return [r[0] for r in self.q(
            "SELECT handle FROM follows WHERE ts<? AND mutual=0 AND unfollowed=0", (cut,))]

    def metric_fresh(self, tid, secs):
        r = self.q1("SELECT ts FROM metrics WHERE tid=?", (tid,))
        return bool(r and time.time() - r[0] < secs)
    def seen_trend(self, n, window):
        r = self.q1("SELECT ts FROM trends WHERE name=?", (n,))
        return bool(r and time.time() - r[0] < window)

    def mark_trend(self, n):
        self.w("INSERT OR REPLACE INTO trends VALUES (?,?,0,0)", (n, time.time()))

    def seen_follow(self, h):
        return bool(self.q1("SELECT 1 FROM follows WHERE handle=?", (h,)))

    def mark_follow(self, h):
        self.w("INSERT OR IGNORE INTO follows VALUES (?,?,0,0)", (h, time.time()))

    def mark_mutual(self, h):
        self.w("UPDATE follows SET mutual=1 WHERE handle=?", (h,))

    def mark_unfollowed(self, h):
        self.w("UPDATE follows SET unfollowed=1 WHERE handle=?", (h,))

    def unfollow_due(self, days):
        cut = time.time() - days * 86400
        return [r[0] for r in self.q(
            "SELECT handle FROM follows WHERE ts<? AND mutual=0 AND unfollowed=0", (cut,))]

    def metric_fresh(self, tid, secs):
        r = self.q1("SELECT ts FROM metrics WHERE tid=?", (tid,))
        return bool(r and time.time() - r[0] < secs)
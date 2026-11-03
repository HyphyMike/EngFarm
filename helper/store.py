"""SQLite queue: candidates (tweets worth engaging) and drafts awaiting your approval."""
import sqlite3, time, threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
  tweet_id TEXT PRIMARY KEY, author TEXT, text TEXT, url TEXT,
  likes INTEGER DEFAULT 0, created_at TEXT, found_ts REAL,
  status TEXT DEFAULT 'new'            -- new | drafted | dismissed
);
CREATE TABLE IF NOT EXISTS drafts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT,                           -- reply | quote | post
  target_id TEXT, target_author TEXT, target_text TEXT,
  text TEXT, alternatives TEXT,
  status TEXT DEFAULT 'pending',       -- pending | approved | posted | rejected | failed
  scheduled_ts REAL, posted_ts REAL, posted_id TEXT, error TEXT,
  created_ts REAL
);
"""

class Store:
    def __init__(self, path="engfarm.db"):
        self.lock = threading.Lock()
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.executescript(SCHEMA)
        self.c.commit()

    def _x(self, sql, args=()):
        with self.lock:
            cur = self.c.execute(sql, args)
            self.c.commit()
            return cur

    # candidates
    def add_candidate(self, t):
        self._x("INSERT OR IGNORE INTO candidates(tweet_id,author,text,url,likes,created_at,found_ts)"
                " VALUES (?,?,?,?,?,?,?)",
                (t["id"], t["author"], t["text"], t["url"], t.get("likes", 0),
                 t.get("created_at", ""), time.time()))

    def candidates(self, status="new"):
        return self._x("SELECT * FROM candidates WHERE status=? ORDER BY found_ts DESC LIMIT 100",
                       (status,)).fetchall()

    def candidate(self, tid):
        return self._x("SELECT * FROM candidates WHERE tweet_id=?", (tid,)).fetchone()

    def set_candidate(self, tid, status):
        self._x("UPDATE candidates SET status=? WHERE tweet_id=?", (status, tid))

    # drafts
    def add_draft(self, kind, text, alternatives="", target=None):
        target = target or {}
        cur = self._x("INSERT INTO drafts(kind,target_id,target_author,target_text,text,alternatives,created_ts)"
                      " VALUES (?,?,?,?,?,?,?)",
                      (kind, target.get("id"), target.get("author"), target.get("text"),
                       text, alternatives, time.time()))
        return cur.lastrowid

    def drafts(self, status):
        order = "scheduled_ts" if status == "approved" else "id DESC"
        return self._x(f"SELECT * FROM drafts WHERE status=? ORDER BY {order} LIMIT 200",
                       (status,)).fetchall()

    def draft(self, did):
        return self._x("SELECT * FROM drafts WHERE id=?", (did,)).fetchone()

    def update_draft(self, did, **fields):
        cols = ", ".join(f"{k}=?" for k in fields)
        self._x(f"UPDATE drafts SET {cols} WHERE id=?", (*fields.values(), did))

    def last_scheduled_ts(self):
        r = self._x("SELECT MAX(COALESCE(posted_ts, scheduled_ts)) FROM drafts "
                    "WHERE status IN ('approved','posted')").fetchone()[0]
        return r or 0

    def count_since(self, kinds, since_ts):
        q = ",".join("?" * len(kinds))
        return self._x(f"SELECT COUNT(*) FROM drafts WHERE status IN ('approved','posted') "
                       f"AND kind IN ({q}) AND COALESCE(posted_ts, scheduled_ts) >= ?",
                       (*kinds, since_ts)).fetchone()[0]

    def due(self, now):
        return self._x("SELECT * FROM drafts WHERE status='approved' AND scheduled_ts<=? "
                       "ORDER BY scheduled_ts", (now,)).fetchall()

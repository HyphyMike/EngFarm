"""EngFarm helper: find tweets, draft in your voice, approve, then post.

Nothing goes out without you pressing Approve (or Post on X yourself).
Run:  python app.py   then open http://127.0.0.1:5005
"""
import os, json, time, threading, logging
from pathlib import Path
from datetime import datetime
import yaml
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
load_dotenv(HERE.parent / ".env")        # reuse keys from the folder above if present

from flask import Flask, request, redirect, url_for, render_template_string, flash
import llm, xclient
from store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("engfarm")

def cfg():
    return yaml.safe_load(open(HERE / "config.yaml", encoding="utf-8"))

store = Store(str(HERE / "engfarm.db"))
x = xclient.X()
app = Flask(__name__)
app.secret_key = os.urandom(16)
DAY = 86400

# ---------- scheduling (your pacing rules) ----------

def next_slot(kind):
    p = cfg()["posting"]
    now = time.time()
    slot = max(now, store.last_scheduled_ts() + p["min_gap_minutes"] * 60)
    kinds, cap = ((["reply"], p["max_replies_per_day"]) if kind == "reply"
                  else (["post", "quote"], p["max_posts_per_day"]))
    # if the rolling 24h window ending at `slot` is full, push forward a day at a time
    while store.count_since(kinds, slot - DAY) >= cap:
        slot += DAY / 4
    return slot

def poster_loop():
    while True:
        try:
            for d in store.due(time.time()):
                try:
                    pid = x.post(d["text"],
                                 reply_to=d["target_id"] if d["kind"] == "reply" else None,
                                 quote_id=d["target_id"] if d["kind"] == "quote" else None)
                    store.update_draft(d["id"], status="posted", posted_ts=time.time(), posted_id=pid)
                    log.info("posted draft %s -> %s", d["id"], pid)
                except Exception as e:
                    store.update_draft(d["id"], status="failed", error=str(e)[:500])
                    log.warning("draft %s failed: %s", d["id"], e)
        except Exception as e:
            log.exception("poster loop: %s", e)
        time.sleep(30)

# ---------- routes ----------

@app.route("/")
def home():
    c = cfg()
    return render_template_string(PAGE, tab="inbox", c=c,
                                  candidates=store.candidates("new"),
                                  pending=store.drafts("pending"),
                                  approved=store.drafts("approved"),
                                  posted=store.drafts("posted")[:30],
                                  failed=store.drafts("failed")[:10],
                                  dry=xclient.DRY, fmt=fmt, intent=xclient.intent_url,
                                  json=json)

@app.post("/find")
def find():
    try:
        found = x.search(cfg()["discovery"])
        for t in found:
            store.add_candidate(t)
        flash(f"Found {len(found)} tweets.")
    except Exception as e:
        flash(str(e))
    return redirect(url_for("home"))

@app.post("/add")
def add():
    try:
        store.add_candidate(xclient.lookup_public(request.form["url"]))
    except Exception as e:
        flash(f"Couldn't load that tweet: {e}")
    return redirect(url_for("home"))

@app.post("/draft/<tid>/<kind>")
def draft_for(tid, kind):
    t = store.candidate(tid)
    c = cfg()
    try:
        fn = llm.reply if kind == "reply" else llm.quote
        opts = fn(c, t["author"], t["text"], request.form.get("angle", ""))
        if opts:
            store.add_draft(kind, opts[0], json.dumps(opts),
                            {"id": t["tweet_id"], "author": t["author"], "text": t["text"]})
            store.set_candidate(tid, "drafted")
    except Exception as e:
        flash(f"Drafting failed: {e}")
    return redirect(url_for("home"))

@app.post("/dismiss/<tid>")
def dismiss(tid):
    store.set_candidate(tid, "dismissed")
    return redirect(url_for("home"))

@app.post("/compose")
def compose():
    try:
        opts = llm.post(cfg(), request.form["topic"], request.form.get("style", "take"))
        if opts:
            store.add_draft("post", opts[0], json.dumps(opts))
    except Exception as e:
        flash(f"Drafting failed: {e}")
    return redirect(url_for("home"))

@app.post("/write")
def write_own():
    text = request.form["text"].strip()
    if text:
        store.add_draft("post", text, json.dumps([text]))
    return redirect(url_for("home"))

@app.post("/d/<int:did>")
def act(did):
    d = store.draft(did)
    text = request.form.get("text", d["text"]).strip()[:280]
    action = request.form["action"]
    if action == "reject":
        store.update_draft(did, status="rejected", text=text)
    elif action == "save":
        store.update_draft(did, text=text)
    elif action == "approve":
        if d["kind"] == "reply" and cfg()["posting"].get("reply_mode", "intent") == "intent":
            # you post it yourself from the browser; we just hand you the pre-filled link
            store.update_draft(did, text=text, status="approved", scheduled_ts=None)
        else:
            slot = next_slot(d["kind"])
            store.update_draft(did, text=text, status="approved", scheduled_ts=slot)
            flash(f"Scheduled for {fmt(slot)}.")
    elif action == "posted_manually":
        store.update_draft(did, status="posted", posted_ts=time.time())
    elif action == "unapprove":
        store.update_draft(did, status="pending", scheduled_ts=None)
    return redirect(url_for("home"))

def fmt(ts):
    return datetime.fromtimestamp(ts).strftime("%a %H:%M") if ts else ""

PAGE = """
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EngFarm helper</title>
<style>
:root{--bg:#fafaf9;--card:#fff;--ink:#1c1917;--mute:#78716c;--line:#e7e5e4;--acc:#1d4ed8;--warn:#b45309}
@media (prefers-color-scheme:dark){:root{--bg:#0c0a09;--card:#1c1917;--ink:#f5f5f4;--mute:#a8a29e;--line:#292524;--acc:#60a5fa;--warn:#fbbf24}}
body{background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif;margin:0;padding:16px;max-width:1100px;margin:auto}
h1{font-size:20px;margin:4px 0}h2{font-size:15px;text-transform:uppercase;letter-spacing:.05em;color:var(--mute);margin:24px 0 8px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}@media(max-width:800px){.grid{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:10px}
.mute{color:var(--mute);font-size:13px}.warn{color:var(--warn)}
textarea{width:100%;box-sizing:border-box;min-height:80px;font:inherit;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:8px}
input[type=text],select{font:inherit;padding:6px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink)}
button,.btn{font:inherit;font-size:13px;padding:5px 10px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer;text-decoration:none;display:inline-block}
.primary{background:var(--acc);color:#fff;border-color:var(--acc)}
form.inline{display:inline}.row{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:6px}
.alt{font-size:13px;border-left:3px solid var(--line);padding-left:8px;margin:4px 0;cursor:pointer}
.flash{background:var(--card);border:1px solid var(--warn);padding:8px;border-radius:6px}
</style></head><body>
<h1>EngFarm helper <span class="mute">@{{c.account_handle}}{% if dry %} · <span class="warn">DRY RUN (nothing is really posted)</span>{% endif %}</span></h1>
{% with m = get_flashed_messages() %}{% for x in m %}<p class="flash">{{x}}</p>{% endfor %}{% endwith %}
<div class="grid"><div>

<h2>1 · Find tweets worth engaging</h2>
<div class="card">
 <form method="post" action="/add" class="row"><input type="text" name="url" placeholder="Paste a tweet link" style="flex:1"><button>Add</button></form>
 <form method="post" action="/find" class="row"><button>Find fresh tweets</button><span class="mute">from {{ c.discovery.accounts|join(', ') }} + keywords (needs read API)</span></form>
</div>
{% for t in candidates %}
<div class="card"><div class="mute"><a href="{{t.url}}" target="_blank">@{{t.author}}</a> · {{t.likes}} likes</div>
 <div>{{t.text}}</div>
 <form method="post" class="row" action="/draft/{{t.tweet_id}}/reply">
  <input type="text" name="angle" placeholder="optional angle" style="flex:1">
  <button formaction="/draft/{{t.tweet_id}}/reply">Draft reply</button>
  <button formaction="/draft/{{t.tweet_id}}/quote">Draft quote</button>
  <button formaction="/dismiss/{{t.tweet_id}}">Skip</button>
 </form></div>
{% else %}<p class="mute">Nothing queued. Paste a link or press Find.</p>{% endfor %}

<h2>Write a post</h2>
<div class="card">
 <form method="post" action="/compose" class="row"><select name="style"><option value="take">take</option><option value="question">question</option><option value="lesson">tip</option></select>
  <select name="topic">{% for s in c.topic_seeds %}<option>{{s}}</option>{% endfor %}</select><button>Draft</button></form>
 <form method="post" action="/write"><textarea name="text" placeholder="…or write your own and queue it"></textarea><button>Queue my post</button></form>
</div>

</div><div>

<h2>2 · Review drafts ({{pending|length}})</h2>
{% for d in pending %}
<div class="card"><div class="mute">{{d.kind}}{% if d.target_author %} to @{{d.target_author}}{% endif %}</div>
 {% if d.target_text %}<div class="mute" style="margin:4px 0">“{{d.target_text[:200]}}”</div>{% endif %}
 <form method="post" action="/d/{{d.id}}">
  <textarea name="text" id="t{{d.id}}" maxlength="280">{{d.text}}</textarea>
  {% for a in json.loads(d.alternatives or '[]')[1:] %}<div class="alt" onclick="document.getElementById('t{{d.id}}').value=this.innerText">{{a}}</div>{% endfor %}
  <div class="row"><button name="action" value="approve" class="primary">Approve</button><button name="action" value="save">Save</button><button name="action" value="reject">Reject</button></div>
 </form></div>
{% else %}<p class="mute">No drafts waiting.</p>{% endfor %}

<h2>3 · Approved</h2>
{% for d in approved %}
<div class="card"><div class="mute">{{d.kind}}{% if d.target_author %} to @{{d.target_author}}{% endif %} · {% if d.scheduled_ts %}goes out {{fmt(d.scheduled_ts)}}{% else %}post it yourself{% endif %}</div>
 <div>{{d.text}}</div>
 <form method="post" action="/d/{{d.id}}" class="row">
  {% if not d.scheduled_ts %}<a class="btn primary" target="_blank" href="{{ intent(d.text, d.target_id if d.kind=='reply' else None) }}">Open on X</a><button name="action" value="posted_manually">I posted it</button>{% endif %}
  <button name="action" value="unapprove">Back to drafts</button></form></div>
{% else %}<p class="mute">Nothing approved yet.</p>{% endfor %}

{% if failed %}<h2>Failed</h2>{% for d in failed %}<div class="card"><div>{{d.text}}</div><div class="mute warn">{{d.error}}</div>
 <form method="post" action="/d/{{d.id}}" class="row"><button name="action" value="unapprove">Back to drafts</button></form></div>{% endfor %}{% endif %}

<h2>Posted</h2>
{% for d in posted %}<div class="card mute">{{fmt(d.posted_ts)}} · {{d.kind}} · {{d.text}}</div>{% else %}<p class="mute">Nothing yet.</p>{% endfor %}
</div></div></body></html>
"""

if __name__ == "__main__":
    threading.Thread(target=poster_loop, daemon=True).start()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5005)), debug=False)

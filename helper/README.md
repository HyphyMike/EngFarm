# EngFarm helper

A review-first engagement helper for @CloutSpot. It finds tweets worth
engaging with, drafts replies, quotes and posts in your voice, and only
posts what you approve, through the official X API at your own pace.

## Setup (Windows PowerShell, from this folder)

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    Copy-Item .env.example .env
    notepad .env

Your Venice key is picked up from `..\.env` automatically, so you can leave
`VENICE_API_KEY` blank here. For posting, create an app at
developer.x.com with **Read and Write** permission and paste its four keys.
Leave `DRY_RUN=1` until you've tried it.

    python app.py

Open http://127.0.0.1:5005.

## How you use it

1. **Find.** Paste a tweet link (works with no X read access), or press
   *Find fresh tweets* to search your watched accounts and keywords
   (needs `X_BEARER_TOKEN` on a tier that includes search).
2. **Draft.** Press *Draft reply* or *Draft quote* (add an angle if you
   want). You get three options in your voice. Click one to use it, edit
   freely. *Write a post* drafts original takes from your topic seeds.
3. **Approve.** Approved posts and quotes are spaced at least
   `min_gap_minutes` apart and capped per day, then go out on schedule.
   Approved replies give you an *Open on X* button with the reply
   pre-filled, so you press Post yourself. (Set `reply_mode: api` to send
   them through the API instead, if your tier allows it.)

## Settings (config.yaml)

`voice`, `topic_seeds`, `discovery` (accounts, keywords, freshness, min
likes) and `posting` (daily caps, gap, reply mode). Restart not needed;
it rereads the file on each action.

## Files

`app.py` web UI + scheduler · `llm.py` drafting · `xclient.py` X API ·
`store.py` queue (`engfarm.db`)

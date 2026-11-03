# EngageFarm

Autonomous X engagement bot. Finds trends, joins conversations, posts its
own takes, follows the right people, and tunes itself on what works.

## Quick start (Docker)

    cp .env.example .env      # add your VENICE_API_KEY
    docker compose up -d
    docker compose exec bot python -m browser login
    # set DRY_RUN=0 in .env, then:
    docker compose restart

## Quick start (local)

    python -m venv .venv
    .venv\Scripts\activate        # Windows
    pip install -r requirements.txt
    playwright install chromium
    cp .env.example .env          # add your key
    python -m browser             # log in by hand, once
    python main.py

## Before you run

1. Set `account_handle` in `config.yaml`.
2. Write your own `voice:` block. This is the single biggest lever.
3. Run with `DRY_RUN=1` for 24 hours and read the log.
4. Put "(automated)" in your bio.

## Controls

| Action | Command |
|---|---|
| Pause | `touch PAUSE` |
| Resume | `rm PAUSE` |
| Check | `python -m killswitch` |
| Stop | `docker compose down` |

## Files

`config.yaml` settings · `digests/` daily reports · `snapshots/` backups ·
`state.db` memory · `chrome-profile/` login

## Verify

    python fixtures.py check
    python -m compileall -q .

See USER_GUIDE.md for the plain-language version.
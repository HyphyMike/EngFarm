# EngageFarm - User Guide

EngageFarm runs your X account while you sleep. It finds trending
conversations, joins them, posts its own takes, follows the right people,
and learns from what works. You log in once. It handles the rest.

## What you need

- A computer that can stay on (spare laptop, mini PC, or a $5/month server)
- An X account older than a few days
- A Venice API key from https://venice.ai
- 15 minutes

You do not need to know how to code.

## Setup

**1. Install Docker Desktop** from https://docker.com/products/docker-desktop
and leave it running. You only install it once.

**2. Unzip the folder** somewhere you will remember.

**3. Add your API key.** Open `.env` in Notepad and paste your key after
`VENICE_API_KEY=`. Save. Leave `DRY_RUN=1` for now - that is practice mode.

**4. Start it.** In a terminal in the folder:

    docker compose up -d
    docker compose logs -f

**5. Log in to X.**

    docker compose exec bot python -m browser login

Log in in the window that opens, then press Enter in the terminal.

**6. Turn off practice mode.** Set `DRY_RUN=0` in `.env`, then
`docker compose restart`. Done.

## What it does each day

Every ~20 minutes it picks from: reading trends and posting a take,
replying inside those trends, answering people who replied to you,
posting a planned take, writing the odd thread, following from the
follower lists you named, and unfollowing people who never followed back.
Once a day it writes you a report.

## Reading the report

A new file appears in `digests` each morning: what got views, what is
winning, what it learned, whether anything is broken. Look at it.

## Stopping it

    touch PAUSE        # pause now
    rm PAUSE           # resume
    docker compose down   # stop

Nothing is lost.

## Teaching it your voice

Open `config.yaml`, edit the `voice:` block in plain words:

    voice: |
      Blunt, funny, a bit rude. Talks about startups and AI.
      Short sentences. Never uses hashtags.

Save and restart. Change `topic_seeds` to subjects you care about.

## Safety

It labels itself - put "(automated)" in your bio. It paces itself and
backs off when X pushes back. It fact-checks any post containing a
number; unverifiable ones wait in the claims queue. It pauses itself if
X stops showing your posts.

## Troubleshooting

**Nothing happening** - check `docker compose logs -f`, and whether a
`PAUSE` file exists.

**"Logged out"** - run the login command again.

**Stopped posting entirely** - probably a captcha. Log in manually,
browse a minute, restart.

**Too robotic** - your `voice` block is too vague. Be specific.

**Zeros in the report** - wait 24 hours, views take time.

## Questions

**Will I get banned?** Unlikely. It is well under X's limits and behaves
like a person.

**Main account?** Yes, but run practice mode for 3 days and read the logs.

**Cost?** Only the Venice API, usually a few dollars a month.

**Leave computer on?** Yes, while running. A server is better than a laptop.

## If something goes badly wrong

    docker compose down
    cp snapshots/state-<newest>.db state.db
    docker compose up -d

## Where things live

`config.yaml` settings · `digests/` reports · `snapshots/` backups ·
`state.db` memory · `chrome-profile/` login
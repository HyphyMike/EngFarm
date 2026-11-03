#!/usr/bin/env bash
set -euo pipefail
NAME="engfarm-$(date +%Y%m%d)"
OUT="$HOME/$NAME.zip"
REQUIRED=(main.py store.py schema.sql browser.py scrape.py actions.py jobs.py
  llm.py config.py config.yaml claims.py semantic.py topics.py style.py stance.py
  health.py killswitch.py memory.py bandit.py audience.py planner.py threads.py
  conversation.py peers.py analytics.py digest.py bluesky.py ingest.py outbox.py
  budget.py journal.py job_costs.py resources.py pacing.py amp.py follow.py
  gates.py trends.py scoring.py approve.py replay.py fixtures.py
  requirements.txt Dockerfile docker-compose.yml .env.example README.md USER_GUIDE.md)
missing=0
for f in "${REQUIRED[@]}"; do
  [ -f "$f" ] || { echo "MISSING: $f"; missing=1; }
done
[ "$missing" -eq 0 ] || { echo "aborting"; exit 1; }
TMP="$(mktemp -d)/$NAME"
mkdir -p "$TMP"
rsync -a --exclude='.venv' --exclude='chrome-profile' --exclude='chrome-amp' \
  --exclude='state.db*' --exclude='.env' --exclude='__pycache__' --exclude='dom' \
  --exclude='snapshots' --exclude='digests' --exclude='candidates' --exclude='PAUSE' \
  ./ "$TMP"/
cp .env.example "$TMP/.env"
chmod +x "$TMP/run.sh"
(cd "$(dirname "$TMP")" && zip -qr "$OUT" "$NAME")
echo "done: $OUT"
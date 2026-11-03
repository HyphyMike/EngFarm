#!/usr/bin/env bash
set -e
[ -f .env ] || { echo "copy .env.example to .env and add your key"; exit 1; }
docker compose up -d
sleep 45
docker compose exec bot python -m browser login
echo "press Enter after logging in"
read
sed -i 's/^DRY_RUN=.*/DRY_RUN=0/' .env
docker compose restart
echo "running. logs: docker compose logs -f"
#!/bin/bash
# Pull-based deploy: converge /opt/council-news-bot on origin/master.
# GitHub runners cannot reach this LAN, so the CT polls instead of push-deploys.
# Only fast-forwards: deploys origin/master when it CONTAINS current HEAD
# (protects a temporarily checked-out hotfix branch until merged). A history
# rewrite breaks the ancestor check by design; recover with a manual
# "git reset --hard origin/master" once, then normal service resumes.
set -euo pipefail
cd /opt/council-news-bot
exec 9>/var/lock/council-bot-deploy.lock
flock -n 9 || exit 0
git fetch -q origin master
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/master)
[ "$LOCAL" = "$REMOTE" ] && exit 0
git merge-base --is-ancestor "$LOCAL" origin/master || { echo "$(date -u +%FT%TZ) waiting: master does not yet contain $LOCAL"; exit 0; }
echo "$(date -u +%FT%TZ) deploying $REMOTE (was $LOCAL)"
git reset --hard -q origin/master
# Build explicitly and fail loudly.
docker compose build 2>&1 | tail -2
# --force-recreate guarantees the running container is replaced by the new
# image even when compose considers the service config unchanged (the stale-
# image bug of 2026-07-24).
flock -x -w 600 .ops.lock docker compose up -d --force-recreate --remove-orphans
docker compose run --rm bot alembic upgrade head 2>&1 | tail -1
# Verify deployed code matches master; a stale image would mismatch here.
RUNNING=$(docker compose run --rm bot git rev-parse HEAD 2>/dev/null || echo unknown)
if [ "$RUNNING" != "$REMOTE" ]; then
  echo "$(date -u +%FT%TZ) WARNING: container code $RUNNING != master $REMOTE"
fi
echo "$(date -u +%FT%TZ) deployed $REMOTE"

#!/bin/bash
# Pull-based deploy: converge /opt/council-news-bot on origin/master.
# The host is not reachable from outside, so it polls instead of being pushed to.
#
# Installed as /usr/local/bin/council-bot-pull-deploy and run from cron every
# 10 minutes. After changing this file, copy it there again: the installed
# copy is what runs.
#
# Only fast-forwards: deploys origin/master when it CONTAINS current HEAD
# (protects a temporarily checked-out hotfix branch until merged). A history
# rewrite breaks the ancestor check by design; recover with a manual
# "git reset --hard origin/master" once, then normal service resumes.
#
# A deploy counts as done only when every step has succeeded, recorded in
# .deployed_sha. Before that file existed, a build or start-up failure left
# the checkout on the new commit, so the next run saw nothing to do and the
# old image kept running unnoticed. Now a failed deploy is retried, up to
# MAX_ATTEMPTS times per commit, and reported to the alerts channel.
set -Eeuo pipefail
cd /opt/council-news-bot
exec 9>/var/lock/council-bot-deploy.lock
flock -n 9 || exit 0

MARK=.deployed_sha        # commit that is fully deployed
FAIL=.deploy_failed       # "<commit> <attempts>" for the commit that is failing
MAX_ATTEMPTS=3

now() { date -u +%FT%TZ; }

alert() {
  # Best effort: a deploy must never fail because Discord is unreachable.
  local url
  url=$(sed -n 's/^DISCORD_WEBHOOK_ALERTS=//p' .env 2>/dev/null | tr -d '"'"'" | head -1) || true
  [ -n "${url:-}" ] || return 0
  curl -fsS -m 15 -H 'Content-Type: application/json' \
    -d "{\"username\":\"Council News Wire deploy\",\"content\":\"$1\",\"allowed_mentions\":{\"parse\":[]}}" \
    "$url" >/dev/null 2>&1 || true
}

git fetch -q origin master
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/master)
DEPLOYED=$(cat "$MARK" 2>/dev/null || true)

# First run after this script is installed: the running system is whatever
# was deployed by the old script. Adopt it instead of redeploying.
if [ -z "$DEPLOYED" ] && [ ! -e "$FAIL" ] && [ "$LOCAL" = "$REMOTE" ]; then
  echo "$LOCAL" > "$MARK"
  exit 0
fi

[ "$LOCAL" = "$REMOTE" ] && [ "$DEPLOYED" = "$REMOTE" ] && exit 0

if [ "$LOCAL" != "$REMOTE" ]; then
  git merge-base --is-ancestor "$LOCAL" origin/master || { echo "$(now) waiting: master does not yet contain $LOCAL"; exit 0; }
fi

ATTEMPTS=0
if [ -f "$FAIL" ] && [ "$(cut -d' ' -f1 "$FAIL")" = "$REMOTE" ]; then
  ATTEMPTS=$(cut -d' ' -f2 "$FAIL")
fi
[ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ] && exit 0   # gave up on this commit; a new commit starts afresh

STEP=start
on_fail() {
  local n=$((ATTEMPTS + 1))
  echo "$REMOTE $n" > "$FAIL"
  echo "$(now) FAILED deploying $REMOTE at step '$STEP' (attempt $n of $MAX_ATTEMPTS)"
  if [ "$n" -eq 1 ]; then
    alert "Deploy of ${REMOTE:0:7} failed at step '$STEP'. Retrying. Still running: ${DEPLOYED:0:7}."
  elif [ "$n" -ge "$MAX_ATTEMPTS" ]; then
    alert "Deploy of ${REMOTE:0:7} failed $n times at step '$STEP' and will not be retried. The server may be running old code (${DEPLOYED:0:7}). See /var/log/council_bot_deploy.log."
  fi
}
trap on_fail ERR

echo "$(now) deploying $REMOTE (was ${DEPLOYED:-$LOCAL}), attempt $((ATTEMPTS + 1))"
STEP=checkout
git reset --hard -q origin/master

STEP=build
docker compose build 2>&1 | tail -2

# Scrape jobs hold the shared lock for up to 20 minutes; wait longer than that.
# The database is started if needed but left alone otherwise; only the bot is
# replaced. --force-recreate guarantees the running container uses the new
# image even when compose considers the service unchanged (the stale-image
# bug of 2026-07-24).
STEP=start
flock -x -w 1500 .ops.lock sh -c \
  'docker compose up -d --remove-orphans && docker compose up -d --force-recreate --no-deps bot'

STEP=migrate
docker compose run --rm bot alembic upgrade head 2>&1 | tail -1

# The image must contain the commit just deployed; a stale image fails here.
STEP=verify
RUNNING=$(docker compose run --rm bot git rev-parse HEAD 2>/dev/null || echo unknown)
if [ "$RUNNING" != "$REMOTE" ]; then
  echo "$(now) container code $RUNNING != master $REMOTE"
  false
fi

trap - ERR
echo "$REMOTE" > "$MARK"
rm -f "$FAIL"
[ "$ATTEMPTS" -gt 0 ] && alert "Deploy of ${REMOTE:0:7} succeeded after $ATTEMPTS failed attempt(s)."
echo "$(now) deployed $REMOTE"

# Old images and build cache otherwise grow until the disk is full.
docker image prune -f >/dev/null 2>&1 || true
docker builder prune -f --filter until=168h >/dev/null 2>&1 || true

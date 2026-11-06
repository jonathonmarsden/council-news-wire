# Database Restore Procedure

Two kinds of backup are taken on the production host:

- **Database dump:** a gzipped `pg_dump`, daily, by `/etc/cron.daily/council-bot-backup`,
  written to `/root/backups/council_news_YYYY-MM-DD.sql.gz` (14-day retention). The
  job refuses to keep a dump under 100 KB.
- **Whole-container snapshot:** nightly, by the host's hypervisor backup job.

(These used to come from a GitHub workflow, with a copy kept as an Actions
artifact. That ended when production moved to a host GitHub cannot reach.)

## Restore to the production VPS

```bash
ssh root@<vps-host>
cd /opt/council-news-bot

# 1. Stop everything that writes to the DB (cron jobs take the shared lock;
#    holding it exclusively blocks new jobs while you work)
exec 9>.ops.lock && flock -x 9

# 2. Drop and recreate the database, then load the dump
docker compose exec -T db psql -U councilbot -d postgres \
  -c "DROP DATABASE IF EXISTS council_news;" \
  -c "CREATE DATABASE council_news OWNER councilbot;"
gunzip -c /root/backups/council_news_YYYY-MM-DD.sql.gz | \
  docker compose exec -T db psql -U councilbot -d council_news

# 3. Bring schema up to date (no-op if the dump matches current code)
docker compose run --rm bot alembic upgrade head

# 4. Sanity check
docker compose exec -T db psql -U councilbot -d council_news \
  -c "SELECT count(*) AS articles, max(posted_at) AS last_post FROM articles;"

# 5. Release the lock (or just close the shell)
exec 9>&-
```

## Restore after losing the container

1. Restore the latest whole-container snapshot with the host's backup tools, or
   provision a new container (`scripts/deployment/setup_vps.sh`), copy the repo
   and `.env` across and run `docker compose up -d`.
2. If the snapshot is older than the newest dump, load the dump with the steps
   above from step 2.
3. Reinstall the crontab: `python3 scripts/deployment/generate_crontab.py`, then
   `crontab crontab_generated.txt`.

## Verify a backup without restoring it

```bash
gunzip -t /root/backups/council_news_YYYY-MM-DD.sql.gz          # gzip integrity
gunzip -c /root/backups/council_news_YYYY-MM-DD.sql.gz | head   # looks like SQL?
```

**Test this procedure after any major schema change** — an untested backup is a hope, not a backup.

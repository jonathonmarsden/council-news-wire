# Database Restore Procedure

Backups are gzipped `pg_dump` files created daily by `.github/workflows/ops_monitoring.yml`:

- **On the VPS:** `/opt/council-news-bot/backups/council_news_YYYY-MM-DD.sql.gz` (14-day retention)
- **Off-box:** GitHub Actions artifact `db-backup-<run_id>` on each daily Ops Monitoring run (30-day retention) — this is the copy that survives losing the droplet.

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
gunzip -c backups/council_news_YYYY-MM-DD.sql.gz | \
  docker compose exec -T db psql -U councilbot -d council_news

# 3. Bring schema up to date (no-op if the dump matches current code)
docker compose run --rm bot alembic upgrade head

# 4. Sanity check
docker compose exec -T db psql -U councilbot -d council_news \
  -c "SELECT count(*) AS articles, max(posted_at) AS last_post FROM articles;"

# 5. Release the lock (or just close the shell)
exec 9>&-
```

## Restore from the off-box artifact (droplet lost)

1. Download the artifact from the latest successful **Ops Monitoring** run
   (GitHub → Actions → Ops Monitoring → Artifacts → `db-backup-…`).
2. Provision the new box (see `docs/MIGRATION_TO_home-server.md` / `scripts/deployment/setup_vps.sh`), copy the repo and `.env` across, `docker compose up -d`.
3. `scp` the dump to the server and follow the steps above from step 2.
4. Reinstall the crontab: `python3 scripts/deployment/generate_crontab.py` on the server, then `crontab crontab_generated.txt`.

## Verify a backup without restoring it

```bash
gunzip -t backups/council_news_YYYY-MM-DD.sql.gz          # gzip integrity
gunzip -c backups/council_news_YYYY-MM-DD.sql.gz | head   # looks like SQL?
```

**Test this procedure after any major schema change** — an untested backup is a hope, not a backup.

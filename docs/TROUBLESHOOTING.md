# Troubleshooting & Learnings

## Common Issues & Fixes

### 1. Cloudflare/WAF Blocking ("Error 1005", "Access Denied")

**Symptoms:**
- Scraper returns `0 articles found`.
- `debug_scraper.py` shows HTTPS 200 OK, but content length is small (~600-2000 bytes).
- HTML content contains phrases like "error code: 1005", "access denied", or `cf-browser-verification`.

**Learnings:**
- **Status Codes are Misleading**: Cloudflare often returns status `200` even for blocked requests.
- **Detection**: We must check the response body text for block signatures.
- **Fix Strategy**:
    1.  **Impersonation**: Use `curl_cffi` with recent browser profiles (`chrome120`, `safari15_5`).
    2.  **Proxies**: Enable `use_rotating_proxy: true` in `councils.json`.
    3.  **Headers**: Ensure `User-Agent` matches the impersonated browser accurately.

### 2. Database "Schism" (Historical Data Loss)

**Incident (Dec 5, 2025):**
- A deployment change moved the database location from `./bot.db` (root) to `./data/bot.db` (volume).
- **Result**: Scrapers working on the VPS appeared "Broken" (0 total articles) because they were writing to a fresh DB, while historical data sat orphaned in the old DB.
- **Fix**: Use `scripts/maintenance/merge_databases.py` to consolidate records.
    ```bash
    python3 scripts/maintenance/merge_databases.py --old bot.db --new data/bot.db
    ```

### 3. Docker Memory Kills (Exit Code 137)

**Symptoms:**
- The bot container restarts unexpectedly.
- Logs end abruptly or show `Killed`.

**Fix:**
- Ensured `deploy.resources.limits.memory: 1024M` in `docker-compose.yml`.
- Reduced concurrency in `scheduler.py` from 5 to 2.

### 4. The "Missing Posts" / Freshness Filter Trap

**Symptoms:**
- You fix a broken scraper, it finds 30 articles.
- Database stats show `new: 0`, `archived: 30`.
- The bot posts **nothing**.

**Cause:**
- The system has a hardcoded **7-day freshness filter** (`MAX_ARTICLE_AGE_DAYS = 7` in `main.py`).
- Any article older than 7 days (even if just discovered) is archived immediately.

**Workaround:**
- This is intentional behavior to prevent flooding the feed with "old news".
- If you *must* announce historical items (e.g. reviving a Zombie scraper), use the `--force-fresh` flag:
    ```bash
    python3 main.py --council melbourne --force-fresh
    ```

### 5. Zombie Scrapers (Silent Failure)

**Symptoms:**
- Scraper runs successfully (Status: OK) but consistently returns 0 articles.
- Often caused by layout changes that break selectors without causing a crash.

**Detection:**
- Run `scripts/maintenance/audit_silent_failures.py`.
- Check `consecutive_empty_runs` in `council_health` table.

**Fix:**
- Update selectors in `councils.json`.
- Run with `--force-fresh` to verify fix and announce backlog.

**Symptoms:**
- `scheduler.log` stops abruptly.
- `docker compose logs` shows containers restarting.
- VPS memory usage spikes to 100%.

**Learnings:**
- Running ~5 concurrent Chrome-like scrapers (`curl_cffi` or `playwright`) is memory intensive.
- **Fix**:
    - Increased `memory: 1024M` limit in `docker-compose.yml`.
    - Set `reservations: memory: 128M` to guarantee minimums.

## Deployment Notes

- **VPS IP**: `vps.example.com`
- **User**: `root`
- **Port**: 22 (Standard)
- **Method**: Push-to-Deploy (rsync)
- **Script**: `scripts/deployment/deploy_with_password.py`
- **Secrets**: stored in `scripts/deployment/deploy_secrets.py` (git-ignored).

## Debugging Workflow

1.  **Check Remote State**:
    ```bash
    ssh root@vps.example.com "cd /opt/council-news-bot && docker compose logs --tail=100 bot"
    ```
2.  **Manual Scrape (Test Mode)**:
    ```bash
    ssh root@vps.example.com "cd /opt/council-news-bot && docker compose exec bot python3 main.py --council [id] --scrape-only"
    ```
3.  **Check DB Stats**:
    ```bash
    ssh root@vps.example.com "sqlite3 /opt/council-news-bot/data/bot.db 'select count(*) from articles where council_id=\"[id]\";'"
    ```

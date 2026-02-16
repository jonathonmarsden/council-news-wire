# Council News Bot - Operational Runbook

**Last Updated**: 15 February 2026  
**Version**: 2.0 (Post-Proxy Fix)  
**Audience**: Operations, deployment, maintenance  

**Database**: PostgreSQL only.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Daily Operations](#daily-operations)
3. [Troubleshooting](#troubleshooting)
4. [Emergency Procedures](#emergency-procedures)
5. [Maintenance Tasks](#maintenance-tasks)
6. [Common Issues](#common-issues)

---

## Quick Start

### Check Bot Status

```bash
# SSH to VPS
ssh root@vps.example.com

# Check containers running
docker compose -f /opt/council-news-bot/docker-compose.yml ps

# View recent logs
docker compose -f /opt/council-news-bot/docker-compose.yml logs bot --tail=100
```

### Run a Manual Scrape

```bash
# Single state, dry-run (no posts)
docker compose -f /opt/council-news-bot/docker-compose.yml exec -T bot \
  python main.py --state wa --dry-run

# Single council, full run
docker compose -f /opt/council-news-bot/docker-compose.yml exec -T bot \
  python main.py --state vic --council melbourne --concurrency 2

# With reduced concurrency (morning window)
docker compose -f /opt/council-news-bot/docker-compose.yml exec -T bot \
  python main.py --state nsw --time-window morning --dry-run
```

### Post from Backlog

```bash
# Post articles already scraped but not yet posted
docker compose -f /opt/council-news-bot/docker-compose.yml exec -T bot \
  python main.py --state vic --post-only --limit 10
```

---

## Daily Operations

### Cron Schedule

Bot runs **twice daily** per state (06:00 AM and 6:00 PM local time):

```
# Morning runs (06:00 AM local per state, staggered by 10 min)
00 04 * * * root  /opt/council-news-bot/scripts/cron/run_state.sh nsw morning
10 04 * * * root  /opt/council-news-bot/scripts/cron/run_state.sh vic morning
20 04 * * * root  /opt/council-news-bot/scripts/cron/run_state.sh qld morning
...

# Evening runs (18:00 PM local per state)
00 12 * * * root  /opt/council-news-bot/scripts/cron/run_state.sh nsw evening
10 12 * * * root  /opt/council-news-bot/scripts/cron/run_state.sh vic evening
...
```

**Note**: Times are UTC. Cron adjusts for each state's local timezone automatically via `--time-window` flag.

Monitoring jobs:

```
# Hourly activity summary
0 * * * * cd /opt/council-news-bot && docker compose exec -T bot python3 scripts/monitoring/hourly_briefing.py

# Daily briefing (21:00 UTC)
0 21 * * * cd /opt/council-news-bot && docker compose exec -T bot python3 scripts/monitoring/daily_briefing.py
```

### Morning Tasks

**Before 06:00 UTC:**
1. Check hourly summary in Discord logs
2. Check health report: `scripts/monitoring/daily_briefing.py`
2. Review overnight errors in Discord #alerts channel
3. Validate proxy is working: `curl -x http://REDACTED-rotate:... https://httpbin.org/ip`

### Evening Tasks

**After 18:00 UTC:**
1. Monitor BlueSky feed for posts
2. Check Discord for any scraper errors
3. If errors detected, see [Troubleshooting](#troubleshooting)

### Weekly Tasks

**Monday morning:**
- Run health audit: `python scripts/monitoring/health_check.py`
- Review council selector accuracy
- Check for new council websites or format changes

---

## Troubleshooting

### Problem: "No Articles Found" (Silent Failure)

**Symptoms**: Council scrapes but returns 0 articles

**Diagnosis**:
```bash
# Always appears as 0 articles in output
python main.py --state wa --council joondalup --dry-run
# Output: "Joondalup: Found 0 articles"

# Check logs for actual error
docker logs council_news_bot | grep -i joondalup | tail -20
```

**Common Causes**:
1. **CSS Selectors Changed**: Council redesigned website
   - **Fix**: Update selectors in `states/wa/councils.json`
   
2. **WAF Blocking**: Website behind Cloudflare/Incapsula
   - **Check**: `curl -v https://www.joondalup.wa.gov.au/news/ | head -30`
   - **Fix**: Enable `use_curl: true` or `use_cloudscraper: true` in config

3. **Proxy Issues**: 407 errors
   - **Check**: `curl -x http://REDACTED-rotate:REDACTED@proxy.example.com:80 https://httpbin.org/ip`
   - **Fix**: Update proxy credentials in `.env`

4. **Empty News Page**: Council has no news this week
   - **Diagnosis**: This is actually OK, not an error. If >3 consecutive runs return 0, Discord alerts will trigger.

### Problem: 407 Proxy Authentication Required

**Symptoms**:
```
HTTPSConnectionPool: Tunnel connection failed: 407 Proxy Authentication Required
curl: (56) CONNECT tunnel failed, response 407
```

**Root Cause**: Proxy credentials expired or IP is not whitelisted

**Quick Fix**:
```bash
# Test proxy credentials
curl -x http://REDACTED-rotate:REDACTED@proxy.example.com:80 https://httpbin.org/ip

# If fails: Update .env on VPS
ssh root@vps.example.com
vi /opt/council-news-bot/.env
# Update: COUNCIL_BOT_PROXY and COUNCIL_BOT_ROTATING_PROXY

# Rebuild containers
docker compose down && docker compose up -d
```

**Prevention**:
- Use rotating endpoint (`-rotate` suffix) not standard endpoint
- Check Webshare dashboard for account status/expiry
- Enable proxy health check at startup: `scripts/deployment/check_proxy_health.sh`

### Problem: BlueSky Posts Not Appearing

**Symptoms**: Scraper finds articles, but nothing posted to BlueSky

**Diagnosis**:
```bash
# Check if articles are in the backlog
docker compose exec -T bot python -c "
from core.database import Database
db = Database()
unposted = db.get_unposted_articles('vic')
print(f'Unposted articles: {len(unposted)}')
for article in unposted[:3]:
    print(f'  - {article[\"title\"][:50]}')
"

# Check if poster can authenticate
docker compose exec -T bot python main.py --state vic --post-only --dry-run
```

**Common Causes**:
1. **BlueSky Credentials Invalid**
   - Check `.env`: `BLUESKY_VIC_HANDLE`, `BLUESKY_VIC_PASSWORD`
   - Test: `python -c "from core.poster import BlueSkyPoster; p = BlueSkyPoster('handle', 'pass'); print(p.authenticated)"`

2. **Rate Limited by BlueSky**
   - Default: 24 posts/hour max per account
   - Check: `docker logs council_news_bot | grep -i "rate\|429"`
   - Fix: Reduce `--limit` or `--max-per-council` in cron

3. **Article Validation Failing**
   - Check logs: `docker logs council_news_bot | grep -i "validation\|garbage"`
   - Fix: Review article content, may have invalid characters or structure

### Problem: High Database Disk Usage

**Symptoms**: PostgreSQL data growing rapidly (>500MB)

**Diagnosis**:
```bash
# Check database size
docker compose exec -T db psql -U councilbot -d council_news \
   -c "select pg_size_pretty(pg_database_size('council_news'));"

# Count articles
docker compose exec -T db psql -U councilbot -d council_news \
   -c "select count(*) from articles;"
```

**Common Causes**:
1. **Too many articles retained**: Database keeps 7+ years of articles
   - Check: `select count(*) from articles where date < now() - interval '30 days';`
   - Fix**: Run cleanup: `python scripts/maintenance/cleanup_old_articles.py --keep-days 90`

2. **Duplicate articles**: Same URL inserted many times
   - Fix**: Run dedup: `python scripts/maintenance/deduplicate_articles.py`

**Prevention**:
- Run `scripts/maintenance/cleanup_old_articles.py --keep-days 30` weekly
- Monitor with: `watch -n 3600 "docker compose exec -T db psql -U councilbot -d council_news -c \"select pg_size_pretty(pg_database_size('council_news'));\""`

---

## Emergency Procedures

### Complete Bot Failure

**Symptoms**: All scrapes failing, no posts for 24+ hours

**Action Plan**:
```bash
# 1. Check container status
ssh root@vps.example.com
docker compose -f /opt/council-news-bot/docker-compose.yml ps

# 2. If stopped, restart
docker compose up -d

# 3. Check logs for errors
docker compose logs bot --tail=200 | grep -i error

# 4. If database corrupted
docker compose exec -T bot python scripts/maintenance/check_db.py

# 5. If config broken, reload from git
cd /opt/council-news-bot
git pull origin main
docker compose restart bot
```

### BlueSky Account Compromised

**Immediate Action**:
1. Change BlueSky password
2. Update `.env` on VPS with new password
3. Restart posting: `docker compose exec -T bot python main.py --state vic --post-only`

### Proxy Blacklisted

**Symptoms**: Consistent 403/429 errors from Webshare proxy

**Action**:
```bash
# Rotate proxy IP
# 1. Test if rotation automatic (should be, using -rotate endpoint)
curl -x http://REDACTED-rotate:... https://httpbin.org/ip
curl -x http://REDACTED-rotate:... https://httpbin.org/ip
# Should return different IPs

# 2. If not working, contact Webshare support or upgrade plan
# 3. Temporary workaround: Run without proxy (risky, may get blocked)
ssh root@vps.example.com
# Edit .env, comment out COUNCIL_BOT_PROXY
docker compose restart bot
```

---

## Maintenance Tasks

### Weekly: Health Check

```bash
python scripts/monitoring/health_check.py --state all
# Generates report: reports/health_check_$(date +%Y%m%d).json
```

### Weekly: Selector Audit

```bash
# Test selectors for councils that returned 0 articles
python scripts/maintenance/audit_selectors.py --states wa vic nsw
```

### Monthly: Database Optimization

```bash
# Backup database
docker compose exec -T db pg_dump -U councilbot council_news \
   > /opt/council-news-bot/backups/council_news_$(date +%Y%m%d).sql

# Clean old articles (>30 days)
python scripts/maintenance/cleanup_old_articles.py --keep-days 30

# Optimize database
docker compose exec -T db psql -U councilbot -d council_news -c "VACUUM (ANALYZE);"
```

### Quarterly: Dependency Updates

```bash
# Update Python packages
pip install -U -r requirements.txt

# Rebuild Docker image
docker build -t council-news-bot:latest .

# Test with dry-run
docker compose exec -T bot python main.py --state vic --dry-run
```

---

## Common Issues

### "Module Not Found" on VPS

**Solution**:
```bash
# SSH to VPS
ssh root@vps.example.com

# Check Python version
python --version  # Should be 3.9+

# Reinstall requirements
cd /opt/council-news-bot
pip install -r requirements.txt

# Rebuild Docker (ensures clean env)
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Cron Job Not Running

**Check**:
```bash
# View crontab
crontab -l

# Check if cron service running
systemctl status cron

# Test cron directly
/opt/council-news-bot/scripts/cron/run_state.sh vic morning
```

### Selector Regex Not Matching

**Debug**:
```bash
# Test selector on live page
python << 'EOF'
from bs4 import BeautifulSoup
import requests

url = "https://example.gov.au/news/"
html = requests.get(url).text
soup = BeautifulSoup(html, 'html.parser')

# Test item selector
items = soup.select("div.news-item")
print(f"Found {len(items)} items")

# Test title selector on first item
if items:
    title = items[0].select_one("h2.title")
    print(f"Title: {title.text if title else 'NOT FOUND'}")
EOF
```

### Timezone Issues

**Symptoms**: Posts at wrong times, morning concurrency not applied

**Check**:
```bash
# Verify state timezone mapping
python -c "from core.timezone_utils import STATE_TIMEZONES, get_utc_time; print(STATE_TIMEZONES); print(get_utc_time('VIC', 6, 0))"

# Test time window detection
python main.py --state vic --time-window morning --dry-run
# Should show: "🕐 Morning window detected: Reducing concurrency..."
```

---

## Getting Help

### Log Locations

- **Docker container logs**: `docker logs council_news_bot --tail=200`
- **VPS system logs**: `/var/log/council_bot_scraper.log`
- **Database**: PostgreSQL (`db` service, volume `postgres_data`)

### Key Files for Debugging

- `main.py` — Entry point, contains scraping loop
- `core/scrapers/base.py` — Base scraper class, fetch logic
- `core/database.py` — Database models and queries
- `core/poster.py` — BlueSky posting logic
- `states/{state}/councils.json` — Configuration per council

### Discord Alerts

Bot sends alerts to `#council-news-alerts` channel:
- 🔴 **Scraper Failure**: Council failing for 3+ consecutive runs
- 🟡 **Silent Failure**: Council returned 0 articles
- 🟢 **Success**: Daily summary of posts made

---

## Contact & Escalation

**For Issues**:
1. Check this runbook first (Ctrl+F to search)
2. Check logs: `docker logs council_news_bot --tail=500`
3. Check Discord #alerts for recent errors
4. If still stuck, file issue in GitHub with logs attached

**Maintenance Window**: 
- Preferred: Sunday 00:00-02:00 UTC (low traffic)
- At least 24h notice to stake holders

---

**Version**: 2.0  
**Last Reviewed**: 15 February 2026  
**Next Review**: 22 February 2026

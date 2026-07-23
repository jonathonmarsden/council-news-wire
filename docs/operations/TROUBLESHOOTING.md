# Council News Bot - Troubleshooting Guide

**Last Updated**: 15 February 2026  
**Quick Reference**: For common issues and self-service resolution  

**Database**: PostgreSQL only.

---

## Problem Index

- [Bot Not Scraping](#bot-not-scraping)
- [Proxy Issues (407)](#proxy-issues-407)
- [BlueSky Not Posting](#bluesky-not-posting)
- [Silent Failures (0 Articles)](#silent-failures-0-articles)
- [Database Issues](#database-issues)
- [Performance Issues](#performance-issues)
- [Deployment Issues](#deployment-issues)

---

## Bot Not Scraping

### Issue: Cron Not Running

**Test**:
```bash
# Check if cron service is running
systemctl status cron

# View crontab
crontab -l | grep council-news-bot

# Run cron job directly
/opt/council-news-bot/scripts/cron/run_state.sh vic morning
```

**Fix**:
```bash
# If cron service stopped
systemctl start cron
systemctl enable cron

# If crontab empty, reinstall
crontab /opt/council-news-bot/crontab_generated.txt
```

### Issue: Bot Runs But No Output

**Test**:
```bash
# Check if container is running
docker-compose ps

# View logs
docker-compose logs bot --tail=50
```

**Fix**:
```bash
# If stopped, restart
docker-compose up -d

# If error in logs, read error message carefully
# Most common: missing .env, bad credentials, DB error
```

### Issue: "ModuleNotFoundError: No module named..."

**Test**:
```bash
docker-compose exec bot python -c "import core.scrapers"
```

**Fix**:
```bash
# Reinstall dependencies
docker-compose exec bot pip install -r requirements.txt

# Or rebuild image
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## Proxy Issues (407)

### Issue: "Proxy Authentication Required"

**Error Message**:
```
Tunnel connection failed: 407 Proxy Authentication Required
"The proxy you are connecting is not in your list."
```

**Diagnosis**:
```bash
# Test proxy from command line
curl -v -x http://user:pass@proxy.example.com:port https://httpbin.org/ip

# Expected output: {"origin": "XXX.XXX.XXX.XXX"}
# Error output: 407 response
```

**Fix**:
```bash
# 1. Verify .env file has correct proxy URL
grep COUNCIL_BOT_PROXY /opt/council-news-bot/.env

# 2. Check for common issues
# Missing "-rotate" suffix = IP-restricted endpoint = 407 for VPS
# Old credentials = expired Webshare account = 407

# 3. Update .env with correct rotating endpoint
sed -i 's/REDACTED:/REDACTED-rotate:/g' /opt/council-news-bot/.env

# 4. Restart bot
docker-compose restart bot

# 5. Verify it works
docker-compose exec bot python -c "
import requests
proxies = {'https': 'http://user:pass@proxy.example.com:port'}
r = requests.get('https://httpbin.org/ip', proxies=proxies)
print(r.json())
"
```

### Issue: Proxy Too Slow (>1 second per request)

**Diagnosis**:
```bash
# Measure proxy latency
time curl -s -x http://REDACTED-rotate:... https://httpbin.org/ip
# Should be <500ms
```

**Fix** (in order):
1. Check Webshare dashboard for account health
2. Try different rotating IP:
   ```bash
   # Force IP rotation (make 3 requests, should get different IPs)
   for i in {1..3}; do
     curl -s -x http://REDACTED-rotate:... https://httpbin.org/ip | jq .origin
     sleep 1
   done
   ```
3. Check VPS network (run `iperf` test to Webshare)
4. If persistently slow, enable DNS caching:
   ```bash
   # Add to .env
   PROXY_DNS_CACHE=true
   ```

---

## BlueSky Not Posting

### Issue: "No articles to post" (Backlog Empty)

**Check**:
```bash
# Verify database has articles
docker compose exec -T db psql -U councilbot -d council_news \
   -c "select count(*) from articles;"

# Check for unposted articles
docker compose exec -T db psql -U councilbot -d council_news \
   -c "select count(*) from articles where posted_at is null;"
```

**Likely Cause**: Articles are too old (>7 days)

**Fix**:
```bash
# Force post old articles
docker-compose exec bot python main.py --state vic --force-fresh --post-only --limit 5

# Or adjust age check in main.py
```

### Issue: BlueSky Post Fails (401 Unauthorized)

**Test**:
```bash
docker-compose exec bot python -c "
from core.poster import BlueSkyPoster
p = BlueSkyPoster('handle', 'password')
print(f'Authenticated: {p.authenticated}')
print(f'DID: {p.session_token}')
"
```

**Fix**:
```bash
# 1. Verify credentials in .env
grep BLUESKY_VIC_HANDLE /opt/council-news-bot/.env
grep BLUESKY_VIC_PASSWORD /opt/council-news-bot/.env

# 2. Test BlueSky credentials manually
# Go to https://bsky.app and try login
# If fails, reset password, update .env

# 3. Restart bot
docker-compose restart bot

# 4. Retry posting
docker-compose exec bot python main.py --state vic --post-only --limit 1 --dry-run
```

### Issue: (429) Rate Limited

**Error for states that post >20 articles/hour**:
```
HTTP 429 Too Many Requests
```

**Fix**:
```bash
# Reduce posts per state
# Edit cron to add limits:
python main.py --state vic --post-only --limit 15  # Max 15 posts

# Or reduce per-council:
python main.py --state vic --post-only --max-per-council 3  # Max 3 per council

# Wait 1 hour, then retry
sleep 3600
docker-compose exec bot python main.py --state vic --post-only --limit 5
```

---

## Silent Failures (0 Articles)

### Issue: Council Returns 0 Articles

**Symptoms**:
```
City of Joondalup: Found 0 articles
(appears in logs as normal, not an error)
```

**Diagnosis**:
```bash
# 1. Manually visit the council website
curl -s "https://www.joondalup.wa.gov.au/news/" | head -100

# 2. Check if website exists and has content
# If blank/error page = website down or changed format

# 3. Test scraper directly
docker-compose exec bot python << 'EOF'
from core.scrapers.factory import ScraperFactory
import json

with open('states/wa/councils.json') as f:
    config = json.load(f)
    council = [c for c in config['councils'] if c['id'] == 'joondalup'][0]

scraper = ScraperFactory.create_scraper(council)
articles = scraper.scrape()
print(f"Found: {len(articles)}")
for a in articles[:3]:
    print(f"  - {a.title}")
EOF
```

**Common Causes & Fixes**:

1. **CSS Selectors Changed** (Council redesigned website)
   ```bash
   # Inspect website with browser dev tools
   # Find new selectors
   # Update states/wa/councils.json
   # Test: docker-compose exec bot python main.py --state wa --council joondalup --dry-run
   ```

2. **Website Behind WAF** (Cloudflare/Akamai)
   ```bash
   # Enable curl_cffi
   # Edit states/wa/councils.json
   # Set: "use_curl": true, "scraper": "curl_scraper"
   # Test: docker-compose exec bot python main.py --state wa --council joondalup --dry-run
   ```

3. **News Page is Actually Empty**
   ```bash
   # Check manually: visit website, is there news?
   # If truly empty, this is OK
   # Discord alert only triggers if 3+ consecutive runs return 0
   ```

4. **Proxy Blocked** (407 errors)
   ```bash
   # Check logs for 407
   docker logs council_news_bot | grep "407\|Proxy.*Required"
   # Fix: See [Proxy Issues (407)](#proxy-issues-407) section
   ```

---

## Database Issues

### Issue: Database connection failed

**Symptoms**:
```
psql: error: could not translate host name "db" to address
psql: error: connection refused
```

**Cause**: Database container down, wrong `DATABASE_URL`, or cron using `docker compose run` instead of `exec`.

**Fix**:
```bash
# 1. Check DB container
docker compose ps db

# 2. Validate DB connectivity
docker compose exec -T db psql -U councilbot -d council_news -c "select 1;"

# 3. Confirm cron uses exec (not run)
crontab -l | grep process_global_queue
```

### Issue: Database Growing Too Large (>500MB)

**Diagnosis**:
```bash
# Check database size
docker compose exec -T db psql -U councilbot -d council_news \
   -c "select pg_size_pretty(pg_database_size('council_news'));"

# Count articles
docker compose exec -T db psql -U councilbot -d council_news \
   -c "select count(*) from articles;"
```

**Fix**:
```bash
# Backup first
docker compose exec -T db pg_dump -U councilbot council_news \
   > /opt/council-news-bot/backups/council_news_$(date +%Y%m%d).sql

# Delete articles older than 90 days
docker compose exec -T db psql -U councilbot -d council_news \
   -c "delete from articles where date < now() - interval '90 days';"

# Optimize database
docker compose exec -T db psql -U councilbot -d council_news -c "vacuum (analyze);"

# Check new size
docker compose exec -T db psql -U councilbot -d council_news \
   -c "select pg_size_pretty(pg_database_size('council_news'));"
```

### Issue: Missing Tables

**Symptoms**:
```
relation "articles" does not exist
```

**Fix**:
```bash
# Run migrations
cd /opt/council-news-bot
docker compose exec -T bot alembic upgrade head

# If migrations fail, restore from latest pg_dump backup
ls -lt /opt/council-news-bot/backups/*.sql | head -5
```

---

## Performance Issues

### Issue: Scraping Takes >20 Minutes

**Diagnosis**:
```bash
# Check proxy latency
time curl -s -x http://REDACTED-rotate:... https://httpbin.org/ip

# Check Docker resource limits
docker stats council_news_bot

# Check database query times
docker compose exec -T db psql -U councilbot -d council_news \
   -c "select council_id, avg(duration_ms)::int as avg_ms from scraper_stats 
    where run_at > now() - interval '7 days' 
    group by council_id 
    order by avg_ms desc limit 10;"
```

**Fix** (in order):
1. Reduce concurrency: `--concurrency 3`
2. Check proxy (see [Proxy Issues](#proxy-issues-407))
3. Disable non-essential features (e.g., detailed logging)
4. Scale up DB resources or prune old rows
5. Add more workers: `--concurrency 12`

### Issue: Posts Not Posting (Backlog Growing)

**Check**:
```bash
# Count unposted articles
docker compose exec -T db psql -U councilbot -d council_news \
   -c "select count(*) from articles where posted_at is null;"

# Check for posting errors
docker logs council_news_bot | tail -100 | grep -i "post\|bluesky"
```

**Fix**:
```bash
# Force post from backlog
docker-compose exec bot python main.py --state vic --post-only --limit 20

# If rate limited (429), wait 1 hour then retry
# If auth error (401), update BlueSky credentials in .env
# If validation error, skip article:
#   docker compose exec -T db psql -U councilbot -d council_news \
#     -c "update articles set status='invalid' where id=XXX;"
```

---

## Deployment Issues

### Issue: Docker Build Fails

**Error**: `pip install` fails

**Fix**:
```bash
# 1. Update base image
docker pull python:3.10

# 2. Rebuild with verbose output
docker build -t council-news-bot . --no-cache --progress=plain

# 3. Check requirements.txt for compatibility
pip install -r requirements.txt  # Test locally first
```

### Issue: Docker Compose Can't Start

**Test**:
```bash
docker-compose config  # Check YAML syntax
docker-compose up --abort-on-container-exit  # See error details
```

**Common Fixes**:
```bash
# Missing .env file
touch .env
# Copy from template
cp .env.example .env
# Fill in values

# Docker daemon not running
systemctl start docker
```

### Issue: Can't Connect to PostgreSQL

**Test**:
```bash
# From inside container
docker compose exec -T db psql -U councilbot -d council_news -c "select 1;"

# From host
psql -h vps.example.com -U councilbot -d council_news
```

**Fix**:
```bash
# Check if DB container running
docker-compose ps db

# Check logs
docker-compose logs db | tail -20

# Reset database
docker-compose restart db
```

---

## Still Stuck?

**Before asking for help**, gather:
```bash
# 1. Full error message (last 20 lines of logs)
docker logs council_news_bot --tail=50 > /tmp/bot_logs.txt

# 2. System info
docker-compose ps > /tmp/docker_ps.txt
docker-compose version >> /tmp/docker_ps.txt

# 3. Configuration (hide secrets)
grep -v PASSWORD /opt/council-news-bot/.env > /tmp/env_config.txt

# 4. Recent scraper runs
docker compose exec -T db psql -U councilbot -d council_news \
   -c "select * from scraper_stats order by run_at desc limit 10;" > /tmp/scraper_runs.txt
```

Share `/tmp/bot_logs.txt` and system info in issue.

---

**If none of these help**, see:
- `docs/operations/RUNBOOK.md` — Full operations guide
- `docs/operations/MONITORING.md` — Health checks & metrics
- `docs/architecture/SYSTEM_DESIGN.md` — How the system works
- GitHub Issues — Search for your error message

---

**Last Updated**: 15 February 2026  
**Version**: 1.0

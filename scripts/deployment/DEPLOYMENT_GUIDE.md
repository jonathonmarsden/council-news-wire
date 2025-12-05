# Council News Bot - Deployment Guide

## Quick Start

### Deploy to Production VPS

```bash
# Full deployment with all checks
./scripts/deployment/deploy.sh

# Dry run (see what would be deployed)
./scripts/deployment/deploy.sh --dry-run

# Skip pre-flight checks (not recommended)
./scripts/deployment/deploy.sh --skip-checks
```

## Pre-Deployment Checklist

The deployment script automatically checks:

- ✅ Git repository status
- ✅ Python dependencies installed
- ✅ JSON config file validity
- ✅ VPS connectivity
- ✅ Docker availability on VPS
- ✅ Enabled councils count
- ✅ `.env.example` sanitized (no real credentials)
- ✅ Scraper modules load correctly

## What Gets Deployed

### Included:
- Python source code (`*.py`)
- Configuration files (`states/*/councils.json`, `states/*/config.json`)
- Dependencies list (`requirements.txt`)
- Docker configuration (`Dockerfile`, `docker-compose.yml`)
- Scheduler (`scheduler.py`)

### Excluded (not synced):
- `.git/` - Git repository
- `__pycache__/`, `*.pyc` - Python bytecode
- `.env` - Local environment (VPS has its own)
- `council_news.db*` - Local database (VPS maintains its own)
- `*.log` - Log files
- `venv/` - Virtual environment
- `.vscode/`, `.idea/` - IDE configs
- `backups/` - Backup files
- `debug_*.html` - Debug files
- `scripts/deployment/deploy_secrets.py` - Credentials

## Deployment Flow

1. **Pre-flight Checks** (10 validation steps)
2. **Backup VPS Database** (timestamped, keeps last 10)
3. **Deploy Code** (rsync with progress)
4. **Restart Services** (Docker Compose rebuild)
5. **Verify Deployment** (health checks)
6. **Show Summary** (useful commands)

## VPS Management Commands

### View Live Logs
```bash
ssh root@vps.example.com
cd /opt/council-news-bot
docker compose logs -f
```

### Check Service Status
```bash
ssh root@vps.example.com "cd /opt/council-news-bot && docker compose ps"
```

### Restart Services
```bash
ssh root@vps.example.com "cd /opt/council-news-bot && docker compose restart"
```

### Stop Bot
```bash
ssh root@vps.example.com "cd /opt/council-news-bot && docker compose down"
```

### Start Bot
```bash
ssh root@vps.example.com "cd /opt/council-news-bot && docker compose up -d"
```

### View Database Stats
```bash
ssh root@vps.example.com
cd /opt/council-news-bot
docker compose exec council-bot python3 -c "
from core.database import Database
db = Database()
print(f'Total articles: {len(db.get_all_articles())}')
"
```

### Manual Health Check
```bash
ssh root@vps.example.com
cd /opt/council-news-bot
python3 scripts/audit_lga_coverage.py
```

## Rollback Procedure

If deployment fails:

1. **Restore previous database backup:**
   ```bash
   ssh root@vps.example.com
   cd /opt/council-news-bot/backups
   ls -lt  # Find the backup you want
   cp council_news_backup_YYYYMMDD_HHMMSS.db ../council_news.db
   ```

2. **Revert code (if needed):**
   ```bash
   # On local machine
   git log --oneline -10  # Find the commit to revert to
   git checkout <commit-hash>
   ./scripts/deployment/deploy.sh
   ```

3. **Restart services:**
   ```bash
   ssh root@vps.example.com "cd /opt/council-news-bot && docker compose restart"
   ```

## Troubleshooting

### Deployment Script Fails

**Issue:** `sshpass: command not found`
```bash
# macOS
brew install hudochenkov/sshpass/sshpass

# Linux
sudo apt-get install sshpass
```

**Issue:** `deploy_secrets.py not found`
- Ensure `scripts/deployment/deploy_secrets.py` exists with VPS credentials:
  ```python
  HOST = "vps.example.com"
  USER = "root"
  PASS = "your-vps-password"
  ```

**Issue:** VPS connection timeout
- Check VPS is online
- Verify firewall allows SSH (port 22)
- Test: `ping vps.example.com`

### Container Won't Start

**Check logs:**
```bash
ssh root@vps.example.com "cd /opt/council-news-bot && docker compose logs --tail=100"
```

**Common issues:**
- Missing `.env` file on VPS
- Port conflicts (check with `docker ps`)
- Insufficient memory (check with `docker stats`)

**Rebuild from scratch:**
```bash
ssh root@vps.example.com
cd /opt/council-news-bot
docker compose down
docker system prune -f
docker compose up -d --build
```

### Database Issues

**Check database size:**
```bash
ssh root@vps.example.com "ls -lh /opt/council-news-bot/council_news.db*"
```

**Reset database (⚠️ DANGER - loses all data):**
```bash
ssh root@vps.example.com
cd /opt/council-news-bot
docker compose down
mv council_news.db council_news.db.old
docker compose up -d
```

## Post-Deployment Monitoring

### First 5 Minutes
- ✅ Watch logs for errors: `docker compose logs -f`
- ✅ Check scheduler starts: Look for "Starting scrape for..." messages
- ✅ Verify posting begins: Look for "Posted:" messages

### First Hour
- ✅ Check BlueSky feeds for new posts
- ✅ Verify all states are scraping
- ✅ Monitor container memory usage: `docker stats`

### First 24 Hours
- ✅ Run health check: `python3 scripts/audit_lga_coverage.py`
- ✅ Check for disabled councils (circuit breaker triggered)
- ✅ Review posting frequency (should be ~every 5 min during 5am-10pm)

## Environment Variables on VPS

The VPS must have a `.env` file with real credentials:

```bash
# Location: /opt/council-news-bot/.env
BLUESKY_HANDLE_NSW=roundupnewsbotnsw.bsky.social
BLUESKY_PASSWORD_NSW=<real-app-password>
BLUESKY_HANDLE_VIC=roundupnewsbotvic.bsky.social
BLUESKY_PASSWORD_VIC=<real-app-password>
# ... etc for all states
COUNCIL_BOT_PROXY=<proxy-url>
COUNCIL_BOT_ROTATING_PROXY=<rotating-proxy-url>
```

**Never commit this file to git!**

## Scheduler Behavior

- **Scrape Job:** Every 3 hours, all states
- **Post Job:** Every 5 minutes (5am-10pm AEST only)
- **Concurrency:** 2 workers (to prevent VPS overload)
- **Timeout:** 1 hour per scrape job

## Success Metrics

### Healthy Deployment Shows:
- ✅ Container running (`docker compose ps` shows "Up")
- ✅ No Python exceptions in logs
- ✅ Regular "Scraping X councils..." messages
- ✅ Regular "Posted: ..." messages during active hours
- ✅ Database growing (new articles added)
- ✅ BlueSky feeds updating

### Warning Signs:
- ⚠️ Container restarts frequently
- ⚠️ "Circuit breaker" messages (councils disabled after 5 failures)
- ⚠️ No posts during active hours (5am-10pm)
- ⚠️ Python exceptions in logs
- ⚠️ Database not growing

## Support & Debugging

### Check Current Coverage
```bash
python3 scripts/audit_lga_coverage.py
```

### Test Single Council
```bash
python3 main.py --state vic --councils ballarat --scrape-only --dry-run
```

### View Circuit Breaker Status
```bash
python3 -c "
from core.database import Database
db = Database()
disabled = [c for c in db.get_all_council_health() if c['is_disabled']]
print(f'Disabled councils: {len(disabled)}')
for c in disabled:
    print(f\"  - {c['council_id']}: {c['consecutive_failures']} failures\")
"
```

### Reset Circuit Breaker for Council
```bash
python3 -c "
from core.database import Database
db = Database()
db.reset_health('<council-id>')
print('Circuit breaker reset')
"
```

## Emergency Contacts

- **VPS Provider:** DigitalOcean / Vultr (check hosting)
- **Repository:** https://github.com/jonathonmarsden/council-news-bot
- **BlueSky Accounts:** See `.env` for handles

---

**Last Updated:** 5 December 2025  
**Bot Version:** 2.0 (Multi-state, Circuit Breaker, 99.4% Coverage)

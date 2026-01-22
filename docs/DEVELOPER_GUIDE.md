# Developer Guide

This guide provides detailed information for developers maintaining and extending the Council News Bot.

## 📂 Project Structure

The project has been reorganized for better maintainability:

```text
council-news-bot/
├── core/                   # Core Application Logic
│   ├── config.py           # Central configuration (Paths, Env Vars)
│   ├── database.py         # SQLite database handler
│   ├── scraper.py          # Scraper implementations
│   ├── poster.py           # BlueSky API client
│   └── utils.py            # Logging and utilities
├── states/                 # Configuration by State
│   ├── vic/councils.json   # VIC Council configurations
│   ├── nsw/councils.json   # NSW Council configurations
│   └── ...
├── scripts/                # Utility scripts (Categorized)
│   ├── maintenance/        # Routine tasks (health checks, cleanup)
│   ├── deployment/         # VPS deployment tools
│   ├── analysis/           # Data analysis & diagnosis tools
│   ├── one_off/            # Single-use migration scripts
│   └── debug/              # Specific scraper debuggers
├── tests/                  # Unit tests
│   └── manual/             # Archived manual test scripts
├── _archived_old_code/     # Deprecated files
├── main.py                 # CLI Entry Point
└── scheduler.py            # Main Service Loop (runs on VPS)
```

## ⚙️ Configuration

The project uses a central configuration module `core/config.py`.
**Do not hardcode paths.** Always import `DB_PATH`, `PROJECT_ROOT`, or `CONFIG_PATHS` from `core.config`.

### Environment Variables (`.env`)
```bash
# Database
DB_PATH=data/bot.db  # Use absolute path or relative to project root

# BlueSky Credentials
BLUESKY_HANDLE_VIC=...
BLUESKY_PASSWORD_VIC=...
# ... (repeat for other states)

# Proxy (Optional)
COUNCIL_BOT_PROXY=http://user:pass@host:port
COUNCIL_BOT_ROTATING_PROXY=http://user:pass@host:port
```

## 🛠️ Common Tasks

### 1. Health Check
Run the global health check to see the status of all scrapers.
```bash
python3 scripts/maintenance/health_check.py
```
This generates `HEALTH_REPORT.md`.

### 2. Diagnosing Dead Scrapers
If scrapers are failing (0 articles), use the diagnosis tool:
```bash
python3 scripts/analysis/diagnose_scrapers.py
```
This tool will:
- Identify "Dead" scrapers.
- Check for WAF blocks (403).
- Check for broken selectors.
- **Auto-fix** by switching to RSS if available.
- Generate `DEAD_SCRAPERS_REPORT.md`.

### 3. Fixing WAF Blocks (403 Forbidden)
Many councils use Cloudflare/Incapsula. To bypass this, we use `curl_cffi`.
Run the WAF fixer to automatically enable `use_curl: true` for blocked councils:
```bash
python3 scripts/maintenance/fix_waf_councils.py
```

### 4. Fixing Selectors
If a page loads (200 OK) but finds no articles, the CSS selector is likely wrong.
Run the suggestion tool:
```bash
python3 scripts/analysis/suggest_selectors.py
```
Review `SELECTOR_SUGGESTIONS.md` for potential fixes, then manually update the relevant `councils.json`.

### 5. Adding a New Council
1.  Add the entry to `states/<state>/councils.json`.
2.  Run `python3 main.py --state <state> --scrape-only` to test.
3.  If it fails with 403, add `"use_curl": true`.
4.  If it fails with 0 items, check the selector.

## 🚀 Deployment

The bot runs on a DigitalOcean VPS via Docker Compose.

### Deploying Code

👉 **See [docs/DEPLOYMENT.md](DEPLOYMENT.md) for full deployment instructions.**

### VPS Management
```bash
# SSH into VPS
ssh root@<vps-ip>

# View Logs
cd /opt/council-news-bot
docker compose logs -f --tail=100

# Restart Service
docker compose restart
```

## 🛡️ Safety Mechanisms

- **Max Posts Per Council**: `main.py` defaults to `--max-per-council 5` to prevent flooding the feed if a backlog clears suddenly.
- **Rate Limiting**: The poster sleeps 2 seconds between posts.
- **Duplicate Prevention**: URLs are tracked in `bot.db` and never reposted.

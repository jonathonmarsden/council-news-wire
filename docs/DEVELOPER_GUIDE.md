# Developer Guide

Reference for developers maintaining and extending Council News Bot: project
layout, council configuration schema, collector types, and common commands.

New councils are configuration, not code — see [CONTRIBUTING.md](../CONTRIBUTING.md)
for the workflow of adding or repairing one.

## Repository Layout

```
council-news-bot/
├── main.py                        # CLI entrypoint — scrape + post pipeline
├── core/
│   ├── scrapers/
│   │   ├── base.py                # BaseScraper ABC + NewsArticle dataclass
│   │   ├── card.py                # CardScraper — primary engine (CSS selectors)
│   │   ├── factory.py             # ScraperFactory.create_scraper()
│   │   ├── rss.py                 # RSSScraper
│   │   ├── json.py                # JsonScraper (dot-notation field paths)
│   │   ├── browser.py             # BrowserScraper (Playwright, JS-heavy sites)
│   │   ├── alyka.py               # AlykaScraper (Alyka CMS)
│   │   ├── catalyst.py            # CatalystScraper
│   │   ├── spark_json.py          # SparkNewsListingScraper
│   │   ├── custom.py              # InnerWestScraper, BunburyScraper, WordPressScraper, OpenCitiesScraper, APYScraper, AspNetScraper
│   │   └── wa_custom.py           # WA-specific: WannerooScraper, PerthScraper, ClaremontScraper, JoondalupScraper, BelmontScraper, DumbleyungScraper
│   ├── models.py                  # SQLAlchemy models: Article, CouncilHealth, ScraperStats, LogEvent, RunSummary
│   ├── database.py                # Database class — all DB operations
│   ├── poster.py                  # BlueSkyPoster — ATProto posting
│   ├── validator.py               # Post validation (title, excerpt, URL, hashtags, facets)
│   ├── constants.py               # GARBAGE_TITLES, GENERIC_TITLES, ADDRESS_MARKERS
│   ├── exceptions.py              # Custom exception hierarchy
│   ├── timezone_utils.py          # DST-aware timezone helpers, STATE_TIMEZONES
│   ├── utils.py                   # setup_logging, URL helpers
│   └── config.py                  # Configuration management
├── states/
│   ├── vic/
│   │   ├── config.json            # State-level config (timezone, BlueSky handle env vars, hashtags)
│   │   └── councils.json          # Array of council scraper configs
│   ├── nsw/, qld/, wa/, sa/, tas/, nt/, act/
│   └── hashtags_map.json          # Canonical council hashtags (also at docs/hashtags_map.json)
├── scripts/
│   ├── cron/process_global_queue.py  # Posts from DB queue every 10 min (run by cron)
│   ├── deployment/                   # deploy.sh, generate_crontab.py, rollback scripts
│   └── maintenance/                  # health_check.py, diagnose_failures.py, etc.
├── tests/                         # pytest tests (mix of unit + live integration)
├── alembic/                       # DB migrations
├── docs/                          # Operational docs, hashtags_map.json
├── .github/workflows/             # CI/CD: test.yml, deploy.yml, rollback.yml, ops_monitoring.yml
├── docker-compose.yml             # bot + PostgreSQL 15
├── Dockerfile                     # Playwright + Python 3.10
└── requirements.txt
```

---

## Key Flows

### Full Scrape-and-Post Run
```
python main.py --state vic
```
1. `load_state_config('vic')` — reads `states/vic/config.json` + `councils.json`
2. `scrape_councils()` — ThreadPoolExecutor (4–8 workers), shuffled council order
3. Per council: circuit breaker check → `ScraperFactory.create_scraper()` → `scraper.scrape()`
4. `process_articles()` — content quality filter (`is_valid_article`), 7-day staleness check, bulk upsert to DB
5. `post_articles()` — BlueSky auth, per-council rate limit (max 5/run), 2s delay between posts

### Posting Queue (runs every 10 min via cron)
```
python scripts/cron/process_global_queue.py
```
Round-robin by council, 18 posts/hr per state account.

### Adding a New Council
1. Add entry to `states/{state}/councils.json`
2. Set `"enabled": true` and choose `"scraper"` type
3. Test: `python main.py --state {state} --council {id} --dry-run`

---

## Council Config Reference

Each entry in `councils.json`:

```jsonc
{
  "id": "ballarat",              // Unique kebab-case ID
  "name": "Ballarat City Council",
  "news_url": "https://...",
  "scraper": "curl_scraper",     // See scraper types below
  "enabled": true,
  "population": 119036,          // Metadata only
  "region": "Central Highlands", // Metadata only

  // Selector config — TWO equivalent styles (both supported):
  // FLAT style:
  "item_selector": ".card.card--news",
  "title_selector": ".title",
  "date_selector": ".date",
  "link_selector": "self",       // "self" = the card element itself is the link

  // NESTED style (alternative):
  "selectors": {
    "container": ".card.card--news",
    "title": ".title",
    "date": ".date",
    "link": "self"
  },

  // WAF bypass flags (pick one or combine):
  "use_curl": true,              // curl_cffi with browser impersonation
  "use_cloudscraper": true,      // cloudscraper (Cloudflare-specific)
  "mobile_mode": true,           // iPhone User-Agent

  // Impersonation profile (used with use_curl):
  // Allowed values: "chrome110", "chrome120", "chrome124", "safari15_5"
  "impersonate": "chrome124",

  // Proxy control:
  "use_rotating_proxy": true,    // Use COUNCIL_BOT_ROTATING_PROXY env var
  "bypass_proxy": true,          // Skip proxy entirely for this council

  // Content control:
  "skip_excerpt": true,          // Don't include excerpt in BlueSky post
  "limit": 5                     // Max articles to scrape per run
}
```

**Scraper types** registered in `ScraperFactory`:
- `card_scraper` / `curl_scraper` — `CardScraper` (CSS selectors; curl_scraper = CardScraper with `use_curl=True`)
- `rss_scraper` — `RSSScraper`
- `json_scraper` — `JsonScraper` (dot-notation field paths)
- `browser_scraper` — `BrowserScraper` (Playwright)
- `alyka_scraper`, `catalyst_scraper`, `spark_news_listing_scraper` — CMS-specific
- `wordpress_scraper`, `opencities_scraper`, `aspnet_scraper`, `apy_scraper` — platform-specific
- `inner_west_scraper`, `bunbury_scraper` — council-specific
- `wanneroo_scraper`, `perth_scraper`, `claremont_scraper`, `joondalup_scraper`, `belmont_scraper`, `dumbleyung_scraper` — WA custom

---

## Database Models

| Table | Purpose |
|-------|---------|
| `articles` | News articles. `url` is UNIQUE (primary dedup key). `date` is `DateTime`. `status`: `new` → `posted` or `archived` |
| `council_health` | Per-council circuit breaker state. Disabled after `consecutive_failures >= 5` |
| `scraper_stats` | Per-run telemetry per council |
| `log_events` | Structured log entries (event_type, severity, JSON metadata) |
| `run_summaries` | Aggregated per-run stats |

Migrations: `alembic upgrade head` (run automatically on container start).

---

## Environment Variables

```
DATABASE_URL=postgresql://councilbot:password@db:5432/council_news

# One set per state:
BLUESKY_HANDLE_VIC=roundupnewsbotvic.bsky.social
BLUESKY_PASSWORD_VIC=xxxx-xxxx-xxxx-xxxx

# Proxies (optional):
COUNCIL_BOT_PROXY=http://user:pass@host:port
COUNCIL_BOT_ROTATING_PROXY=http://user:pass@rotating-host:port

# Discord webhooks (optional — all logging degrades gracefully if absent):
DISCORD_WEBHOOK_LOGS=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_ALERTS=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_FEED=https://discord.com/api/webhooks/...
```

---

## Common Commands

```bash
# Full run for a state
python main.py --state vic

# Test a single council (no posting)
python main.py --state vic --council ballarat --dry-run

# Post from existing backlog only (skip scrape)
python main.py --state vic --post-only

# Scrape only (don't post)
python main.py --state vic --scrape-only

# Force post old articles (bypass 7-day filter)
python main.py --state vic --force-fresh

# Custom concurrency
python main.py --state vic --concurrency 8

# Run tests
pytest tests/

# Generate production crontab (run after DST transitions)
python scripts/deployment/generate_crontab.py

# Health check
python scripts/maintenance/health_check.py
```

---

## Known Technical Debt

- ~41 councils in the scraper repair backlog (see `docs/SCRAPER_REPAIR_PLAYBOOK.md`)
- Several WA custom scraper classes are CardScraper/Alyka configs in disguise — consolidation plan in `docs/CODE_REVIEW_2026-07-07.md` (REFACTOR-1)
- Deferred review findings (QUAL-7 URL normalization, QUAL-11 tz normalization, QUAL-14 hardcoded endpoints) — see the review doc's status ledger

---

## Deployment

Production runs on **home-server the container** (unprivileged Debian LXC, Docker Compose, 4GB/2vCPU). Access: `ssh user@server` (hypervisor host, private network) then `bash`. App at `/opt/council-news-bot`, secrets at `/root/secrets/.env`.

**Deploys are pull-based**: merging to master is deploying. `/usr/local/bin/council-bot-pull-deploy` (cron, every 10 min on the CT) fast-forwards to origin/master, rebuilds, and swaps containers under the ops lock. There is no push-deploy; GitHub runners cannot reach the LAN.

Backups: daily in-container `pg_dump` (`/etc/cron.daily/council-bot-backup` → `/root/backups/`, 14-day retention) plus nightly hypervisor `vzdump` of the whole CT (7 daily + 4 weekly). Restore: `docs/operations/RESTORE.md`. Rollback: `pct rollback 104 <snapshot>` or `git revert` + let pull-deploy converge.

```bash
# Docker rebuild (inside the container)
docker compose up -d --build
```

Cron schedule is generated by `scripts/deployment/generate_crontab.py` (no args). It emits a **complete** crontab — staggered once-daily scrape slots (UTC, DST-independent: no regeneration needed at DST transitions) plus the infra lines (posting queue, watchdog, alerts, digest, cleanup). Install the whole file: `crontab crontab_generated.txt`. Scrape jobs are `--scrape-only`; **all posting flows through the queue processor**.

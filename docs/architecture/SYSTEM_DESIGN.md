# Council News Bot - System Architecture & Design

**Version**: 2.0 (Post-Proxy Overhaul)  
**Last Updated**: 15 February 2026  
**Audience**: Engineers, architects, contributors  

---

## System Overview

```
┌────────────────────────────────────────────────────────────────┐
│                      COUNCIL NEWS BOT                          │
│                     (Production System)                        │
└────────────────────────────────────────────────────────────────┘
        │
        ├─ INPUT LAYER (Data Collection)
        │   ├─ Scraper Engine (core/scrapers/)
        │   │   ├─ CardScraper — HTML-based extraction
        │   │   ├─ CURLScraper — WAF bypass (curl_cffi)
        │   │   ├─ RSSScraper — RSS feed parsing
        │   │   ├─ JsonScraper — JSON API responses
        │   │   ├─ BrowserScraper — JavaScript rendering
        │   │   └─ Custom Scrapers — Council-specific logic
        │   │
        │   └─ Transport
        │       ├─ Direct HTTP/HTTPS (fast, can be blocked)
        │       └─ Webshare Rotating Proxy (reliable, IP rotation)
        │
        ├─ PROCESSING LAYER (Data Transformation)
        │   ├─ Database (SQLAlchemy + SQLite/PostgreSQL)
        │   │   ├─ Article deduplication (by URL)
        │   │   ├─ State history (7 years)
        │   │   ├─ Scraper run logs (performance monitoring)
        │   │   └─ Council health tracking (failure detection)
        │   │
        │   └─ Validation Engine
        │       ├─ Garbage title filtering
        │       ├─ Date parsing (DD/MM/YYYY)
        │       └─ Article freshness check (7 days)
        │
        ├─ OUTPUT LAYER (Publishing)
        │   ├─ BlueSky Posting
        │   │   ├─ Multi-account (one per state: VIC, NSW, etc.)
        │   │   ├─ Text truncation & hashtags
        │   │   └─ Rate limiting (24 posts/hour per account)
        │   │
        │   └─ Discord Alerts
        │       ├─ Failure notifications
        │       ├─ Real-time feed
        │       └─ Daily summaries
        │
        └─ ORCHESTRATION (Scheduling)
            ├─ Cron (System scheduler)
            │   ├─ 06:00 local time (morning run)
            │   └─ 18:00 local time (evening run)
            │
            └─ Dynamic Concurrency
                ├─ Morning peak: 4 workers (06:00-08:30 local)
                ├─ Off-peak: 8 workers (other times)
                └─ Staggered starts (10min per state, prevent overload)
```

---

## Architecture Layers

### 1. Scraper Engine (`core/scrapers/`)

Responsible for **data collection** from council websites.

**Components**:
- `base.py` — `BaseScraper` abstract class
  - `fetch_page()` — HTTP request handling with proxy support
  - `_fetch_with_requests()` — Standard requests library
  - `_fetch_with_curl()` — curl_cffi for WAF bypass
  - `_fetch_with_cloudscraper()` — Cloudflare bypass
  - `parse_html()` — BeautifulSoup wrapper
  - `parse_date()` — Custom date parsing (dayfirst=True)

- `factory.py` — `ScraperFactory`
  - Creates appropriate scraper type based on council config
  - Passes HTML selectors, proxy settings, user-agent spoofing
  - Returns configured scraper instance

- Scraper types:
  - `CardScraper` — CSS selectors for HTML cards (most councils)
  - `RSSScraper` — Parses RSS feeds
  - `JsonScraper` — Extracts from JSON APIs
  - `BrowserScraper` — Uses Playwright for JS-rendered pages
  - Custom scrapers — Council-specific extraction logic
    - `JoondalupScraper` — WA custom logic
    - `PerthScraper` — WA custom logic
    - `CatalystScraper` — Catalyst CMS extraction
    - etc.

**Proxy Usage**:
- Standard proxy (`COUNCIL_BOT_PROXY`) — Direct connection
- Rotating proxy (`COUNCIL_BOT_ROTATING_PROXY`) — IP rotation every request
- **Decision**: Use rotating endpoint (`-rotate` suffix) for cloud deployments

**Configuration Format** (`states/{state}/councils.json`):
```json
{
  "id": "joondalup",
  "name": "City of Joondalup",
  "news_url": "https://...",
  "scraper": "curl_scraper",  // or "card_scraper", "json_scraper", etc.
  "use_curl": true,
  "use_rotating_proxy": false,
  "selectors": {
    "container": "div.news-item",
    "title": "h2.title",
    "link": "a.news-link",
    "date": "p.date"
  },
  "enabled": true
}
```

**Concurrency**:
- Scrapers run in ThreadPoolExecutor
- Morning: 4 workers (08:30 local), Off-peak: 8 workers
- Configured via `--concurrency` flag (default 5)

---

### 2. Data Processing (`core/`)

**Database** (`core/database.py`):
- SQLAlchemy ORM with SQLite (dev) / PostgreSQL (prod)
- Tables:
  - `articles` — Scraped news (URL as unique key)
  - `scraper_runs` — Execution history + metrics
  - `council_health` — Failure tracking (circuit breaker)

- Key Methods:
  - `insert_article()` — Upsert with deduplication
  - `mark_as_posted()` — Track published articles
  - `get_unposted_articles()` — Fetch backlog
  - `record_failure()` — Track errors, disable on 5 consecutive failures
  - `log_scraper_run()` — Performance metrics

**Validation** (`main.py` `is_valid_article()`):
- Filters garbage titles (e.g., "Untitled", "New")
- Removes generic content (e.g., "Click here to continue")
- Checks date is parseable
- Ensures URL is not duplicate

**Date Handling** (`core/utils.py`, `core/timezone_utils.py`):
- Always parse with `dayfirst=True` (Australian format DD/MM/YYYY)
- Timezone aware: each state has own TZ (VIC = Australia/Melbourne, etc.)
- DST transitions automatically handled by `pytz` library
- Cron times converted via `get_cron_time()` function

---

### 3. Publishing (`core/poster.py`)

Handles **posting to BlueSky**.

**Components**:
- `BlueSkyPoster` class
  - `authenticate()` — Login with credentials
  - `post_article()` — Create post with text + hashtags
  - Rate limiting — Max 24 posts/hour per account

**Text Formatting**:
- Title + URL (max 300 chars)
- Optional excerpt (space allowing)
- Hashtags (#councils, state + council specific)
- Link cards (auto-generated from URL)

**Multi-Account Support**:
- Each state has separate BlueSky account
- Credentials: `BLUESKY_{STATE}_HANDLE`, `BLUESKY_{STATE}_PASSWORD`
- Env vars configured per state in `states/{state}/config.json`

**Error Handling**:
- 429 Too Many Requests → Backoff + retry later
- 401 Unauthorized → Log error, skip this run
- Network timeout → Retry up to 3x

---

### 4. Orchestration

**Scheduling** (`scripts/cron/`):
- System cron (not Python scheduler)
- Twice daily per state: 06:00 AM and 6:00 PM local time
- Staggered by 10 minutes (VIC, then NSW, then QLD, etc.) to prevent DB contention

**Example Crontab**:
```cron
# Morning runs (UTC times for 06:00 local per state)
00 04 * * * root python main.py --state nsw --time-window morning  # 6:00 AM AEDT
10 04 * * * root python main.py --state vic --time-window morning  # 6:00 AM AEDT
20 04 * * * root python main.py --state qld --time-window morning  # 6:00 AM AEST
```

**Time Window Handling** (`core/timezone_utils.py`):
- `--time-window morning` → Use reduced concurrency (4 workers)
- `--time-window evening` → Use standard concurrency (8 workers)
- Auto-detected if not provided (checks state's local time)
- Prevents morning peak load from causing timeouts

**Dynamic Concurrency**:
```
Morning window (06:00-08:30 local):
  - NSW, VIC, QLD all starting in short window
  - Reduce to 4 workers per state
  - Prevent DB lock/API overload

Off-peak (all other times):
  - Use 8 workers per state
  - Faster scraping, less contention
```

---

## Data Flow

### Scraping Pipeline

```
Start → Load Config → For Each Council (Concurrent):
  1. Fetch page (HTTP, maybe via proxy)
  2. Parse HTML/JSON/RSS with selectors
  3. Extract articles (title, link, date)
  4. Validate article metadata
  5. Check if URL exists in DB (dedup)
  6. If new → Insert into DB
  7. Log run (success/error, duration)
→ End
```

### Posting Pipeline

```
Start → Get Unposted Articles → For Each Article:
  1. Check article age (<7 days? or force-fresh flag)
  2. Validate article still valid
  3. Check per-council post limit (max 5 per run)
  4. Format post text + hashtags
  5. POST to BlueSky API
  6. If success → Mark as posted
  7. If rate limited → Backoff, try later
  8. Log to Discord (success/error)
→ End
```

---

## Key Design Decisions

### Why Proxy?

**Problem**: Councils may block scrapers (seen in logs: rate limits, 403)  
**Solution**: Webshare rotating proxy distributes requests across IP pool  
**Trade-off**: Cost (~$20/mo) vs. reliability (near 100% success)  
**Decision**: Use rotating endpoint (`-rotate` suffix) for cloud deployments

### Why ThreadPoolExecutor (Not Multiprocessing)?

**Reason**: I/O bound (network requests), not CPU bound  
**Benefit**: Shared database connection, lower memory overhead  
**Concurrency limit**: 4-8 workers (not 100+) to respect target websites

### Why SQLite (Dev) / PostgreSQL (Prod)?

**SQLite (Local Development)**:
- Zero setup, file-based
- Sufficient for testing
- Limitations: Single-writer, slow under concurrency

**PostgreSQL (Production VPS)**:
- Multiple concurrent writers
- Better performance at scale (125K+ articles)
- Can be backed up/restored

### Why Twice Daily (Not Continuous)?

**Original**: Every 3 hours (8 runs/day)  
**Problem**: Rate limiting, server load, cost  
**New**: Twice daily (06:00 AM, 6:00 PM local)  
**Benefit**: Councils update ~once daily, matches pattern  
**Trade-off**: Users see updates max 12 hours after publish

### Why Separate BlueSky Accounts Per State?

**Reason**: Each state's news audience is different  
**Benefit**: Fine-grained rate limiting, audience segmentation  
**Implementation**: Separate handle + password per state  
**Hashtags**: #NSW-Local-Government, #VIC-Local-Government, etc.

---

## Failure Modes & Recovery

### Silent Failures (0 Articles)

**Cause**: CSS selectors no longer match website  
**Detection**: >3 consecutive 0-article runs → Discord alert  
**Recovery**: Update selectors in `states/{state}/councils.json`  
**Prevention**: Weekly selector audits

### Proxy 407 (IP Blocked)

**Cause**: VPS IP not whitelisted for standard endpoint  
**Recovery**: Use rotating endpoint (already done)  
**Prevention**: Always use `-rotate` suffix for cloud deployments

### Rate Limiting (429)

**Cause**: Posted >24 articles/hour to BlueSky  
**Recovery**: Backoff for 15 minutes, retry  
**Prevention**: Adjust `--max-per-council` or `--limit`

### Database Locked

**Cause**: Multiple writers concurrent access  
**Recovery**: Automatic retry with exponential backoff  
**Prevention**: Use PostgreSQL in production (not SQLite)

### WAF Blocking (403, Cloudflare)

**Cause**: Website detects scripting, blocks scraper  
**Recovery**: Use curl_cffi or cloudscraper for that council  
**Detection**: Logs show block page content  
**Prevention**: Enable `use_curl` in config for known WAF sites

---

## Performance Characteristics

### Scraping

| Metric | Value | Notes |
|--------|-------|-------|
| **Councils per run** | 97-150 | Varies by state |
| **Concurrency** | 4-8 workers | Dynamic, time-based |
| **Duration per state** | 10-15 min | Depends on proxy latency |
| **Articles per day** | 300-500 | Varies by state |
| **Success rate** | 85-95% | >3 consecutive failures = disabled |

### Posting

| Metric | Value | Notes |
|--------|-------|-------|
| **Backlog size** | 50-200 articles | Varies by state |
| **Posts per run** | 5-20 | Limited by `--max-per-council` |
| **BlueSky rate limit** | 24/hour | Hard limit, enforced by API |
| **Posting latency** | 2-5 sec/post | Includes rate limiting delay |

### Database

| Metric | Value | Notes |
|--------|-------|-------|
| **Total articles** | 125K+ | 7+ years of history |
| **DB size** | 100-300 MB | Depends on cleanup frequency |
| **Query latency** | <100ms | Indexed by URL, council_id |

---

## Testing & Validation

### Unit Tests (`tests/`)

```bash
# Test timezone conversions
pytest tests/test_timezone_conversion.py -v

# Test cron schedule generation
pytest tests/test_cron_schedule.py -v
```

### Integration Tests

```bash
# Dry-run scraper without posting
python main.py --state vic --dry-run

# Test scraper for specific council
python main.py --state vic --council melbourne --dry-run

# Test posting without scraping
python main.py --state vic --post-only --dry-run --limit 5
```

### Selector Validation

```bash
# Test CSS selectors on live site
python scripts/maintenance/validate_selectors.py --state wa --council joondalup
```

---

## Deployment

### Docker

```dockerfile
# Dockerfile builds Python 3.9+ image with:
# - All dependencies (requests, beautifulsoup4, curl_cffi, etc.)
# - Source code (/opt/council-news-bot)
# - Database migrations (alembic)
```

### Docker Compose

```yaml
# Runs two services:
# - bot: Main application container
# - db: PostgreSQL database
# Shares .env for credentials
```

### VPS Deployment

```bash
# 1. SSH to VPS
ssh root@vps.example.com

# 2. Code at /opt/council-news-bot
cd /opt/council-news-bot

# 3. Credentials in .env
cat .env | grep COUNCIL_BOT_PROXY

# 4. Run with docker-compose
docker-compose up -d

# 5. Cron jobs configured at system level
crontab -l | grep council-news-bot
```

---

## Dependencies

**Core**:
- `requests` — HTTP library
- `beautifulsoup4` — HTML parsing
- `dateutil` — Date parsing (AU format support)
- `sqlalchemy` — ORM
- `psycopg2` — PostgreSQL driver
- `pytz` — Timezone handling

**Optional**:
- `curl_cffi` — WAF bypass
- `cloudscraper` — Cloudflare bypass
- `playwright` — Browser automation (BrowserScraper)
- `feedparser` — RSS parsing

**External**:
- Webshare proxy (rotating IPs)
- BlueSky API (posting)
- PostgreSQL (production DB)

---

## Future Improvements

**Phase 3 Candidates**:
1. **Kubernetes Deployment** — Horizontal scaling
2. **Elasticsearch** — Full-text search on articles
3. **GraphQL API** — Query articles programmatically
4. **Web Dashboard** — Visualize scraping stats
5. **Email Subscriptions** — Users subscribe to council updates
6. **Mobile App** — iOS/Android native discovery

---

**Document Version**: 2.0  
**Last Reviewed**: 15 February 2026  
**Next Review Date**: 1 May 2026 (Quarterly)

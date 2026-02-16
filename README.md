# Council News Bot

Automated scraper and BlueSky poster for Australian local government news and media releases.

**Live:** [@roundupnewsbot.bsky.social](https://bsky.app/profile/roundupnewsbot.bsky.social)

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)]()
[![Coverage](https://img.shields.io/badge/councils-540%2F541-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.9+-blue)]()

> **Latest Update (Feb 2026):** Transitioned to twice-daily scraping schedule (06:00 & 18:00 local per state) with dynamic concurrency reduction during morning peak. Reduced load by 75% while maintaining coverage. See [SCHEDULING_GUIDE.md](SCHEDULING_GUIDE.md) for details.

## Overview

Council News Bot monitors news pages from local councils across **all 8 Australian States & Territories**:
*   **Victoria (VIC)** - 79 councils
*   **New South Wales (NSW)** - 128 councils
*   **Queensland (QLD)** - 77 councils
*   **Western Australia (WA)** - 138 councils
*   **Tasmania (TAS)** - 29 councils
*   **South Australia (SA)** - 68 councils
*   **Northern Territory (NT)** - 18 councils
*   **Australian Capital Territory (ACT)** - 1 entity

**100% configured** (538/538 available councils in codebase).
*   **Healthy Status (Jan 22, 2026):** 87.2% (469 councils) actively returning news.
*   **State Health:** TAS (100%), ACT (100%), VIC (97.5%), SA (89.9%), QLD (89.7%), NSW (87.5%), NT (83.3%), WA (76.1%).
*   **Scraper Strategy:** Uses a mix of `curl` (VIC, QLD, NSW) and custom CMS scrapers (WA Catalyst, OpenCities) to maximize reliability.

It automatically posts new articles to BlueSky for [LG News Roundup](https://lgnewsroundup.com).

It is designed to be resilient, scalable, and polite:
*   **Resilient**: Uses `curl_cffi` to bypass WAFs (Cloudflare/Incapsula).
*   **Scalable**: Scrapes concurrently and supports hundreds of councils.
*   **Polite**: "Drips" posts out slowly to avoid flooding the feed.

## Features

- **Multi-State Support**: VIC, NSW, QLD, TAS, SA, NT, ACT, WA.
- **WAF Bypass**: Advanced impersonation of real browsers to scrape protected sites.
- **Common CMS Support**: Dedicated scrapers for OpenCities, Catalyst, and WordPress sites.
- **"Record Everything"**: Tracks all articles (even old ones) to monitor scraper health.
- **Automated Posting**: Runs 24/7 on VPS via Docker.
- **BlueSky Integration**: Posts with clickable titles, excerpts, and hashtags.
- **Link Attribution**: Automatically appends UTM parameters (`utm_source=lgnewsroundup.com`, `utm_content=[feed_handle]`) to promote the service and identify traffic sources for councils.
- **Post Validator**: Enforces title/excerpt length, hashtag count/order, URL hygiene, and facet spans before posting.
- **Canonical Hashtags**: State peaks plus per-council tags are generated from configs (`docs/hashtags_map.json`).
- **Deduplication**: Tracks posted articles to avoid duplicates.

## Documentation

*   **[Developer Guide](docs/DEVELOPER_GUIDE.md)**: Setup, testing, and contribution workflow.
*   **[Deployment Guide](docs/DEPLOYMENT.md)**: How to deploy changes to the live VPS.
*   **[AI Context](docs/AI_CONTEXT.md)**: Architecture overview for AI agents.
*   **[Roadmap](docs/ROADMAP.md)**: Future plans and current status.

## Quick Start

### Option 1: Docker (Recommended)

```bash
# 1. Clone the repo
git clone https://github.com/jonathonmarsden/council-news-bot.git
cd council-news-bot

# 2. Create .env file
cp .env.example .env
# Edit .env with your BlueSky credentials

# 3. Run with Docker Compose
docker compose up -d --build
```

### Option 2: Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run a scrape for Victoria
python main.py --state vic

# 3. Run a specific council (debug mode)
python main.py --council warrnambool --dry-run
```

## Project Structure

> **For Developers:** Please refer to `docs/DEVELOPER_GUIDE.md` for detailed architecture, workflows, and debugging guides.

```text
council-news-bot/
├── core/                   # Core Application Logic (Scrapers, DB, Poster)
├── states/                 # Configuration by State (JSON files)
├── scripts/                # Utility scripts (maintenance, deployment, analysis)
├── main.py                 # CLI Entry Point
└── docker-compose.yml      # Orchestration; cron triggers runs
```

## Commands

```bash
# Run full scrape and post (defaults to VIC)
python main.py

# Scrape specific state
python main.py --state nsw

# Dry run (scrape but don't post)
python main.py --dry-run

# Debug a specific council
python main.py --council warrnambool --dry-run

# Post without scraping (for backlog clearing)
python main.py --post-only
```

## Deployment

The bot is deployed on a DigitalOcean VPS running Ubuntu.
Production deploys run via GitHub Actions. Local SSH deploys are break-glass only.
See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment instructions.

## Scheduling (Twice-Daily)

As of February 2026, the bot runs on a **twice-daily schedule** per state:
- **Morning:** 06:00 local time (with reduced concurrency during 06:00–08:30 to manage load)
- **Evening:** 18:00 local time (with standard concurrency)

Each state's times are automatically adjusted for daylight savings and local timezone offset.

For comprehensive scheduling details, timezone handling, and DST management, see [SCHEDULING_GUIDE.md](SCHEDULING_GUIDE.md).

To generate the production crontab:
```bash
python3 scripts/deployment/generate_crontab.py --static
```

## Council Status

Run `python3 scripts/maintenance/daily_health_check.py` to generate the latest health report.

## License

MIT License

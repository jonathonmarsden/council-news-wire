# Council News Bot

Automated scraper and BlueSky poster for Australian local government news and media releases.

**Live:** [@roundupnewsbot.bsky.social](https://bsky.app/profile/roundupnewsbot.bsky.social)

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)]()
[![Coverage](https://img.shields.io/badge/coverage-73%25-yellow)]()
[![Python](https://img.shields.io/badge/python-3.9+-blue)]()

## Overview

Council News Bot monitors news pages from local councils across **Victoria**, **New South Wales**, and **Queensland**. It automatically posts new articles to BlueSky for [LG News Roundup](https://lgnewsroundup.com).

It is designed to be resilient, scalable, and polite:
*   **Resilient**: Uses `curl_cffi` to bypass WAFs (Cloudflare/Incapsula).
*   **Scalable**: Scrapes concurrently and supports hundreds of councils.
*   **Polite**: "Drips" posts out slowly to avoid flooding the feed.

## Features

- **Multi-State Support**: VIC, NSW, QLD (expanding to all of Australia).
- **WAF Bypass**: Advanced impersonation of real browsers to scrape protected sites.
- **"Record Everything"**: Tracks all articles (even old ones) to monitor scraper health.
- **Automated Posting**: Runs 24/7 on VPS via Docker.
- **BlueSky Integration**: Posts with clickable titles, excerpts, and hashtags.
- **Deduplication**: Tracks posted articles to avoid duplicates.

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
└── scheduler.py            # Main Service Loop
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
See `docs/DEPLOY_TO_DIGITALOCEAN.md` for deployment instructions.

## Council Status

Run `python3 scripts/maintenance/daily_health_check.py` to generate the latest health report.

## License

MIT License

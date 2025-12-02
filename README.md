# Council News Bot

Automated scraper and BlueSky poster for Victorian local government news and media releases.

**Live:** [@roundupnewsbot.bsky.social](https://bsky.app/profile/roundupnewsbot.bsky.social)

## Overview

Council News Bot monitors news pages from Victorian local councils and automatically posts new articles to BlueSky for [LG News Roundup](https://lgnewsroundup.com). It tracks press releases, media statements, community announcements, and other council news.

## Features

- **27 Victorian Councils** - Currently enabled and posting (79 configured)
- **Automated Posting** - Runs 24/7 on VPS
- **BlueSky Integration** - Posts with clickable titles, excerpts, and hashtags
- **Deduplication** - Tracks posted articles to avoid duplicates
- **Priority Queuing** - New articles posted before backlog items
- **7-Day Freshness** - Only posts articles from the last week
- **Multiple Scraper Patterns** - Handles various council website structures

## Post Format

```text
[Clickable Title]

[Excerpt if available]
[Council Name]
Published: [Date if available]
#LGNewsRoundup #VLGA #VicCouncils #CouncilName
```

## Project Structure

> **For Developers & AI Agents:** Please refer to `AI_CONTEXT.md` for detailed architecture, workflows, and debugging guides.

```text
council-news-bot/
├── main.py                 # CLI Entry Point (legacy/manual usage)
├── scheduler.py            # Main Service Loop (runs on VPS)
├── core/                   # Core Application Logic
│   ├── scraper.py          # Scraper implementations (BaseScraper, CardScraper)
│   ├── database.py         # SQLite database handler
│   ├── poster.py           # BlueSky API client
│   └── utils.py            # Logging and utilities
├── states/                 # Configuration by State
│   ├── vic/
│   │   └── councils.json   # VIC Council configurations
│   └── nsw/
│       └── councils.json   # NSW Council configurations
├── scripts/                # Utility scripts
└── bot.db                  # SQLite Database (stores article history)
```

## Commands

```bash
# Run full scrape and post
python main.py

# Dry run (scrape but don't post)
python main.py --dry-run

# Post without scraping (for overnight backlog clearing)
python main.py --post-only

# Scrape specific council
python main.py --council cardinia

# Limit posts per run
python main.py --limit 1

# Test BlueSky connection
python main.py --test

# Run tests
pytest
```

## Environment Variables

- `BLUESKY_HANDLE` - BlueSky handle (roundupnewsbot.bsky.social)
- `BLUESKY_PASSWORD` - BlueSky app password

## Deployment

The bot is deployed on a DigitalOcean VPS running Ubuntu. It uses `systemd` to ensure continuous operation.

See `AI_CONTEXT.md` for deployment details.

## Council Status

| Category | Count | Description |
|----------|-------|-------------|
| Enabled | 27 | Actively scraping and posting |
| Direct Access | 21 | Simple HTTP requests |
| Redirect | 10 | Follow redirects |
| WAF Protected | 46 | Requires curl bypass (most disabled) |
| URL Issues | 2 | Needs investigation |

## State Management

The bot maintains state in `bot.db` (SQLite):

- **Articles Table**: Stores URLs, titles, dates, and posting status.
- **Deduplication**: Ensures we don't post the same article twice.

## BlueSky Account

- **Display Name:** LG News Roundup Newsfeed
- **Handle:** @roundupnewsbot.bsky.social
- **Owner:** Chris Eddy (LG News Roundup)

## Related Projects

- [council-bot](https://github.com/jonathonmarsden/council-bot) - Council meeting documents bot

## License

MIT License

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

> **For Developers:** Please refer to `docs/DEVELOPER_GUIDE.md` for detailed architecture, workflows, and debugging guides.

```text
council-news-bot/
├── core/                   # Core Application Logic
├── states/                 # Configuration by State
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

# Post without scraping (for backlog clearing)
python main.py --post-only

# Limit posts per council (Safety Valve)
python main.py --max-per-council 5
```

## Environment Variables

See `docs/DEVELOPER_GUIDE.md` for full configuration details.

## Deployment

The bot is deployed on a DigitalOcean VPS running Ubuntu.
See `docs/DEVELOPER_GUIDE.md` for deployment instructions.

## Council Status

Run `python3 scripts/maintenance/health_check.py` to generate the latest `HEALTH_REPORT.md`.


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

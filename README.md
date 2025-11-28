# Council News Bot

Automated scraper and BlueSky poster for Victorian local government news and media releases.

**Live:** [@roundupnewsbot.bsky.social](https://bsky.app/profile/roundupnewsbot.bsky.social)

## Overview

Council News Bot monitors news pages from Victorian local councils and automatically posts new articles to BlueSky for [LG News Roundup](https://lgnewsroundup.com). It tracks press releases, media statements, community announcements, and other council news.

## Features

- **27 Victorian Councils** - Currently enabled and posting (79 configured)
- **Automated Posting** - Runs every 5 minutes via GitHub Actions (temporary for backlog clearing)
- **BlueSky Integration** - Posts with clickable titles, excerpts, and hashtags
- **Deduplication** - Tracks posted articles to avoid duplicates
- **Priority Queuing** - New articles posted before backlog items
- **7-Day Freshness** - Only posts articles from the last week
- **Multiple Scraper Patterns** - Handles various council website structures

## Post Format

```
[Clickable Title]

[Excerpt if available]
[Council Name]
Published: [Date if available]
#LGNewsRoundup #VLGA #VicCouncils #CouncilName
```

## Project Structure

```
council-news-bot/
├── main.py                 # Main entry point and orchestration
├── poster.py               # BlueSky posting with facets for clickable links
├── requirements.txt        # Python dependencies
├── pytest.ini              # Test configuration
├── config/
│   └── councils.json       # Council configuration (79 councils)
├── scrapers/
│   ├── __init__.py
│   └── base_scraper.py     # BaseScraper, CardScraper, NewsArticle
├── data/
│   └── posted_articles.json # State: posted URLs, known URLs, last post time
├── tests/
│   └── test_scrapers.py    # Unit tests
└── .github/
    └── workflows/
        └── scrape.yml      # GitHub Actions workflow
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

## GitHub Actions

The workflow runs automatically with:
- **Schedule:** Every 5 minutes (temporary) → will return to 15 minutes
- **Hours:** 24/7 (temporary) → will return to Melbourne business hours (5am-10pm)
- **Concurrency:** Only one run at a time (prevents duplicate posts)
- **Overnight:** Post-only mode (no scraping)

### Required Secrets
- `BLUESKY_HANDLE`
- `BLUESKY_PASSWORD`

## Council Status

| Category | Count | Description |
|----------|-------|-------------|
| Enabled | 27 | Actively scraping and posting |
| Direct Access | 21 | Simple HTTP requests |
| Redirect | 10 | Follow redirects |
| WAF Protected | 46 | Requires curl bypass (most disabled) |
| URL Issues | 2 | Needs investigation |

## State Management

The bot maintains state in `data/posted_articles.json`:
- `posted_urls` - URLs already posted to BlueSky
- `known_urls` - URLs seen in previous scrapes (for priority detection)
- `last_post_time` - Timestamp of last post (for gap enforcement)

New articles (not in `known_urls`) are prioritized over backlog items.

## BlueSky Account

- **Display Name:** LG News Roundup Newsfeed
- **Handle:** @roundupnewsbot.bsky.social
- **Owner:** Chris Eddy (LG News Roundup)

## Related Projects

- [council-bot](https://github.com/jonathonmarsden/council-bot) - Council meeting documents bot

## License

MIT License

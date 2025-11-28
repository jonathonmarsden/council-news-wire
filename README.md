# Council News Bot

Automated scraper and BlueSky poster for Victorian local government news and media releases.

## Overview

Council News Bot monitors news pages from all 79 Victorian local councils and automatically posts new articles to BlueSky. It tracks press releases, media statements, community announcements, and other news published by councils.

## Features

- **79 Victorian Councils** - Comprehensive coverage of all local government areas
- **Automated Scraping** - Runs every 6 hours via GitHub Actions
- **BlueSky Integration** - Posts new articles with council name, title, and link
- **Deduplication** - Tracks posted articles to avoid duplicates
- **Multiple Scraper Patterns** - Handles various council website structures

## Project Structure

```
council-news-bot/
├── main.py                 # Main entry point
├── poster.py               # BlueSky posting logic
├── requirements.txt        # Python dependencies
├── pytest.ini              # Test configuration
├── config/
│   └── councils.json       # Council configuration
├── scrapers/
│   ├── __init__.py
│   └── base_scraper.py     # Base scraper class
├── data/
│   └── posted_articles.json
├── tests/
│   └── test_scrapers.py
└── .github/
    └── workflows/
        └── scrape.yml      # GitHub Actions workflow
```

## Councils by Accessibility

| Category | Count | Description |
|----------|-------|-------------|
| Direct Access | 21 | Simple HTTP requests |
| Redirect | 10 | Follow redirects |
| WAF Protected | 46 | Requires curl bypass |
| URL Issues | 2 | Needs investigation |

## Setup

### Local Development

```bash
# Clone the repository
git clone https://github.com/jonathonmarsden/council-news-bot.git
cd council-news-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export BLUESKY_HANDLE="councilnewsbot.bsky.social"
export BLUESKY_PASSWORD="your-app-password"

# Run the bot
python main.py
```

### GitHub Actions

The bot runs automatically every 6 hours. Required secrets:
- `BLUESKY_HANDLE` - BlueSky handle
- `BLUESKY_PASSWORD` - BlueSky app password

## BlueSky Account

- **Display Name:** Council News Bot
- **Handle:** @councilnewsbot.bsky.social
- **Bio:** Automated posts of news and media releases from Victorian local councils. Not affiliated with any council.

## Related Projects

- [council-bot](https://github.com/jonathonmarsden/council-bot) - Council meeting documents bot

## License

MIT License

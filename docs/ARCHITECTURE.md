# Council News Bot Architecture

## Overview
The Council News Bot is a scalable system designed to scrape news from Australian local government websites and publish updates to social media (BlueSky). It currently supports **8/8 States & Territories** (VIC, NSW, QLD, TAS, SA, NT, ACT, WA), with a design ready to scale to all ~540 councils across Australia.

## System Architecture

```mermaid
graph TD
    subgraph "Configuration"
        Config[states/{state}/councils.json]
    end

    subgraph "Core Logic"
        Cron[Host Cron]
        Factory[Scraper Factory]
        Scraper[Scraper Engine]
        DB[(PostgreSQL Database)]
        Poster[BlueSky Poster]
    end

    subgraph "Scraper Engine"
        Card[CardScraper]
        RSS[RSSScraper]
        Catalyst[CatalystScraper]
        Custom[Custom Scrapers]
        CURL[curl_cffi (WAF Bypass)]
    end

    Config --> Factory
    Cron --> Factory
    Factory --> Scraper
    Scraper --> Card
    Scraper --> RSS
    Scraper --> Catalyst
    Scraper --> Custom
    Card --> CURL
    RSS --> CURL
    Catalyst --> CURL
    
    Scraper -->|Raw Articles| DB
    DB -->|Unposted Articles| Poster
    Poster -->|Status Update| DB
```

## Project Structure

```text
council-news-bot/
├── main.py                 # CLI Entry Point
├── core/                   # Core Application Logic
│   ├── scrapers/           # Modular Scraper Package
│   │   ├── base.py         # Base class & Data models
│   │   ├── card.py         # Standard HTML Card Scraper
│   │   ├── rss.py          # RSS Feed Scraper
│   │   └── factory.py      # Scraper Instantiation Logic
│   ├── database.py         # PostgreSQL Handler
│   ├── poster.py           # BlueSky API Client
│   └── utils.py            # Logging & Helpers
├── states/                 # Configuration by State
│   ├── vic/
│   ├── nsw/
│   └── qld/
├── scripts/                # Maintenance & Deployment Scripts
└── docker-compose.yml      # Container Orchestration
```

## Infrastructure & Constraints

The system is designed to run on a low-cost VPS (DigitalOcean Basic Droplet) with specific resource constraints to ensure stability.

| Resource | Constraint | Implementation |
| :--- | :--- | :--- |
| **Memory** | **3072 MB** | Enforced via Docker Compose `deploy.resources.limits.memory`. Prevents OOM kills affecting the host. |
| **Concurrency** | **Time-window based** | Host cron triggers `main.py` with dynamic concurrency (morning reduced, evening higher). |
| **Disk Storage** | **25 GB** | Docker logs are rotated (`max-size: 10m`, `max-file: 3`) to prevent disk exhaustion. |
| **Network** | **IP Reputation** | Heavy reliance on `curl_cffi` and rotating proxies to mitigate WAF blocks on the datacenter IP. |

## Core Components

### 1. Scraper Engine (`core/scrapers/`)
The scraping logic is modular and handles various website structures and anti-bot protections.

*   **`CardScraper`**: The primary scraper. It targets news "cards" on HTML pages using CSS selectors.
    *   **Browser impersonation**: Uses `curl_cffi` to present a realistic browser TLS fingerprint (`chrome110`, `chrome120`), which many council CMS front-ends require before serving pages to a client.
    *   **Mobile Mode**: Can impersonate an iPhone to get a simpler mobile layout.
*   **`CatalystScraper`**: Specialized class for ~116 WA councils using the Catalyst CMS. It handles their specific table-based layout and date parsing automatically.
*   **`RSSScraper`**: Consumes standard RSS feeds where available.
*   **`ScraperFactory`**: Dynamically instantiates the correct scraper based on the council's configuration.

### 2. Database Strategy ("Record Everything")
We use a **"Record Everything"** strategy to eliminate ambiguity between "broken scraper" and "quiet council".

*   **Schema**:
    *   `articles`: Stores **every** article found.
        *   `status='new'`: Fresh article (< 7 days), queued for posting.
        *   `status='archived'`: Old article (> 7 days), stored for history but ignored by poster.
        *   `status='posted'`: Successfully posted to BlueSky.
    *   `scraper_stats`: Logs every run (articles found, duration, status) for health monitoring.
    *   `council_health`: Circuit Breaker tracks:
        *   `consecutive_failures`: Connection errors (trips at 5).
        *   `consecutive_empty_runs`: "Zombie" detection (Active but finding nothing).

### 3. Posting Engine & Cron
The system is orchestrated to balance throughput with safety.

*   **Host Cron (VPS)**:
    *   **Scrape Jobs**: Twice-daily per state (morning/evening, local time windows).
    *   **Post Jobs**: Every 10 minutes via `scripts/cron/process_global_queue.py`.
    *   **Limits**: Posts max **3 articles** per state per run (18/hr per state).
*   **Poster (`core/poster.py`)**:
    *   **Freshness Filter**: Hard filter rejecting articles >7 days old.
    *   **Variety Logic**: Round-Robin selection ensures no single council dominates the feed.
    *   **Validation**: Rejects malformed content or excerpts >250 chars.

### 4. Configuration (`states/{state}/councils.json`)
Configuration is decoupled from code. Each council is defined by a JSON object:

```json
{
    "id": "warrnambool",
    "name": "Warrnambool City Council",
    "news_url": "https://www.warrnambool.vic.gov.au/news",
    "scraper": "card_scraper",
    "enabled": true,
    "use_curl": true,
    "impersonate": "chrome120",
    "item_selector": ".listing.views-row",
    "title_selector": ".listing_title"
}
```

### 5. Deployment Pipeline
The bot is containerized using Docker for consistent execution across environments.

*   **Local**: Developers run `main.py` or scripts directly.
*   **VPS**:
    *   Code is pushed to GitHub.
    *   `scripts/deployment/deploy_to_vps.sh` connects via SSH.
    *   Updates the code on the VPS.
    *   Rebuilds and restarts the Docker container.
    *   PostgreSQL data is persisted in the `postgres_data` volume.

## Scalability Features

1.  **Concurrency**: `main.py` uses `ThreadPoolExecutor` to scrape multiple councils in parallel (default 5 workers).
2.  **State Partitioning**: Councils are organized by state to allow targeted runs (`--state qld`).
3.  **Circuit Breaker**: Automatically disables councils that fail 5 times in a row to prevent log spam and resource waste.

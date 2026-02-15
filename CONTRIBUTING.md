# Contributing to Council News Bot

We welcome contributions! This guide will help you add new councils, fix broken scrapers, and improve the core bot logic.

## ⚠️ Quality Standards: No Silent Failures
Our core mission is reliability. Scrapers must fail loud rather than fail silent.

1.  **Crucial Selectors**: Ensure your `item_selector` targets exactly what you think it does. If the layout changes, we want an error, not 0 articles.
2.  **Specific Over Generic**: Avoid generic selectors like `.col-12`, `.row`, or `.container` unless absolutely necessary.
3.  **Local Testing**: Always verify with `python3 main.py --council <id> --dry-run` before committing.

## 1. Adding a New Council

The most common task is adding a new council to the system.

### Step 1: Analyze the Website
1.  Find the council's "News" or "Media Releases" page.
2.  Inspect the HTML to identify the "card" or "list item" that contains the news article.
3.  Identify CSS selectors for:
    -   **Item**: The container for a single news entry.
    -   **Title**: The headline text.
    -   **Link**: The `<a>` tag pointing to the full article.
    -   **Date**: (Optional) The publication date.

### Step 2: Update Configuration
Edit `states/{state}/councils.json` (e.g., `states/vic/councils.json`).

**Important**: Ensure the configuration targets *Actual News*.
- Avoid scraping "Lost & Found", "Road Closures", or "Events" pages unless they are part of the main news feed.
- Bad titles (e.g., "Agenda", "2026") are filtered by the global firewall, but it is better to avoid scraping them at the source.

```json
{
    "id": "council-id-kebab-case",
    "name": "Council Name",
    "news_url": "https://www.council.vic.gov.au/news",
    "scraper": "card_scraper",
    "enabled": true,
    "item_selector": "div.news-listing-item",
    "title_selector": "h2.title",
    "date_selector": "span.date",
    "link_selector": "a.read-more"
}
```

### Step 3: Test
Run a dry-run debug for just this council:

```bash
python3 main.py --council council-id-kebab-case --dry-run
```

Check the output:
-   Did it find articles?
-   Are the titles clean?
-   Are the dates parsed correctly?

## 2. Configuration Reference (`councils.json`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique ID (kebab-case). Must be unique across the state. |
| `name` | string | Display name for the council. |
| `news_url` | string | URL to scrape. |
| `scraper` | string | Usually `"card_scraper"` or `"rss_scraper"`. |
| `enabled` | bool | Set to `false` to disable scraping. |
| `item_selector` | string | CSS selector for the article container. |
| `title_selector` | string | CSS selector for the title (relative to item). |
| `link_selector` | string | CSS selector for the link (relative to item). Defaults to `self` if item is `<a>`. |
| `date_selector` | string | CSS selector for the date. |
| `use_curl` | bool | Set `true` to use `curl_cffi` (WAF bypass). |
| `impersonate` | string | Browser profile for `curl_cffi` (e.g., `"chrome110"`, `"chrome120"`). |

## 3. Advanced Scraping

### WAF Bypass (Cloudflare/Incapsula)
If a site returns 403 Forbidden, enable `curl_cffi`:

```json
"use_curl": true,
"impersonate": "chrome120"
```

### Custom Scrapers
If `card_scraper` isn't enough (e.g., complex JavaScript, dates on detail pages), you have options:

#### 1. JSON API Scraper (Preferred for Headless/Next.js)
If the site uses a headless CMS (like Next.js) and calls an API to load news, check the Network tab in DevTools. If you find a JSON response with the news data:

1.  Use `"scraper": "json_scraper"`.
2.  Set `news_url` to the API endpoint URL.
3.  Configure selectors using **dot key paths** (e.g., `fields.title`).

```json
{
    "scraper": "json_scraper",
    "news_url": "https://api.council.gov.au/news",
    "item_selector": "items",           // Path to the list of articles in the JSON
    "title_selector": "fields.title",   // Path to title within an item
    "date_selector": "sys.createdAt",   // Path to date
    "link_selector": "https://council.gov.au/news/{fields.slug}" // Template string supported
}
```

#### 2. Browser Scraper (Heavy JS)
Use `browser_scraper` if content is heavily rendered by React/Vue and no clean API exists. Note: This is slower and resource-intensive.

#### 3. Custom Classes
For bespoke logic:
1.  Create a new file in `core/scrapers/custom.py` (or a new file in that directory).
2.  Inherit from `CardScraper`.
3.  Implement your logic (e.g., override `scrape()` or `_get_date()`).
4.  Register the class in `core/scrapers/factory.py`.
5.  Set `"scraper": "your_custom_scraper_name"` in `councils.json`.

## 4. Adding a New State

1.  Create `states/{new_state}/`.
2.  Create `config.json`:
    ```json
    {
        "state_name": "Western Australia",
        "bluesky_handle_env": "BLUESKY_HANDLE_WA",
        "bluesky_password_env": "BLUESKY_PASSWORD_WA",
        "hashtags": ["#LGAWA", "#WACouncils"]
    }
    ```
3.  Create `councils.json` (empty list initially).
4.  Add environment variables to `.env`.

## 5. Code Style

-   **Docstrings**: Use Google-style docstrings for all functions and classes.
-   **Type Hints**: Use Python type hints (`List`, `Dict`, `Optional`).
-   **Linting**: Keep code clean and readable.

## 6. Database

-   **NEVER** commit `bot.db`.
-   **NEVER** commit `logs/`.
-   **ALWAYS** check `.gitignore` before adding new data files.

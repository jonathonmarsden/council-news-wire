# Contributing to Council News Bot

## Code Review Guidelines

When adding new councils or features, please follow these guidelines to ensure the bot remains robust and scalable.

### 1. Adding a New Council

1.  **Check the State Config**: Go to `states/{state}/councils.json`.
2.  **Add Entry**:
    ```json
    {
        "id": "council-name",
        "name": "Council Name",
        "news_url": "https://...",
        "scraper": "card_scraper",
        "item_selector": "div.news-item",
        "title_selector": "h3",
        "date_selector": "span.date",
        "enabled": true
    }
    ```
3.  **Test**: Run `python3 main.py --state {state} --scrape-only`.
4.  **Verify**: Check the output to ensure titles and dates are parsed correctly.

### 2. Custom Scrapers

If `card_scraper` doesn't work (e.g., dates are on the detail page, or complex JS):

1.  **Create Class**: Add a new class in `core/scraper.py` (or a new file in `scrapers/` if we refactor).
2.  **Inherit**: Inherit from `CardScraper`.
3.  **Register**: Add it to the `scraper_classes` dictionary in `main.py`.
4.  **Update Config**: Set `"scraper": "my_custom_scraper"` in `councils.json`.

### 3. Database & Git

-   **NEVER** commit `bot.db`.
-   **NEVER** commit `logs/`.
-   **ALWAYS** check `.gitignore` before adding new data files.

### 4. Scheduling

-   We aim for a "drip feed" approach.
-   Do not set the scheduler to post more frequently than every 15 minutes.
-   If adding a new state, consider offsetting its scrape time in `scheduler.py`.

## Common Issues & Fixes

-   **403 Forbidden**: The council website is blocking the bot.
    -   *Fix*: Set `"scraper": "curl_scraper"` in `councils.json`.
-   **Missing Dates**: The listing page doesn't show dates.
    -   *Fix*: Use a custom scraper to fetch the detail page (like `InnerWestScraper`).
-   **Duplicate Posts**: The URL changed but the content is the same.
    -   *Fix*: The bot uses URL as the unique ID. If URLs change frequently, we might need a more robust fingerprinting method (future work).

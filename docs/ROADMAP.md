# Roadmap to Mission Success

**Mission Statement:**
> "To provide a comprehensive, real-time, aggregated news feed for every local council in Australia, ensuring high reliability, 100% coverage, and automated resilience."

## 1. The Strategy: "Stabilize, Breach, Expand"

We have identified that while the infrastructure is functional, it is fragile (memory limits, DB schisms) and blocked by sophisticated defenses (Cloudflare in SA/VIC). Our strategy moves from stabilizing the core to cracking these defenses.

## 2. Phase 1: Stabilization & Infrastructure (Active)

*Goal: Ensure the bot stays online 24/7 without crashing or losing data.*

- [x] **Memory Safety**: Increased Docker memory limit to 1024MB (was 512MB) to prevent OOM kills.
- [x] **Data Integrity**: Merged split databases (`bot.db` and `data/bot.db`) to restore history.
- [x] **Disk Hygiene**: Reclaimed 14GB of space via `docker system prune` and log vacuuming (Usage dropped from 77% to 19%).
- [ ] **Automated Maintenance**: Create a weekly cron job to run `docker system prune -f` and `journalctl --vacuum-size=200M`.
- [ ] **Log Management**: Configure Docker logging drivers (`json-file`) with `max-size: 10m` to prevent disk fill-up events.

## 3. Phase 2: The "WAF War" (Critical)

*Goal: Crack the Cloudflare/Incapsula defenses blocking 32+ councils (mostly SA and QLD).*

- [ ] **Adelaide Prototype**: Fix the `City of Adelaide` scraper.
    - *Current status*: Detection works, bypass fails.
    - *Action*: Experiment with headers, TLS fingerprinting, or upgrade to a lightweight headless browser service (e.g., `playwright-python` in a separate container) if `curl_cffi` cannot keep up.
- [ ] **QLD/VIC Audit**: Apply the "Adelaide Fix" to broken Queensland and Victorian councils.
- [ ] **Proxy Optimization**: Review `use_rotating_proxy` flags. Only enable for blocked sites to save bandwidth/latency.
- [ ] **RSS Downgrade Operation**: Systematically convert `card_scraper` instances to `rss_scraper` where possible to avoid WAF entirely.

## 4. Phase 3: Total Coverage (Expansion)

*Goal: Close the 5% coverage gap (mostly in Western Australia).*

- [ ] **WA Gap Fill**: 28 Councils in WA are disabled.
    - Identify the 2-3 common CMS platforms (e.g., "Alyka", "Sitefinity") used by these councils.
    - Build shared scrapers (`AlykaScraper`) rather than 28 individual ones.
- [ ] **National Audit**: Run `generate_national_health_report.py` weekly to catch "silent failures" (councils that stop posting news for >60 days).

## 5. Phase 4: Long-Term optimization (Resilience)

*Goal: Make the system maintainable and scalable.*

- [ ] **Database Migration**: Move from SQLite to **PostgreSQL**.
    - *Why*: SQLite is risky for concurrent writes and harder to inspect remotely. Postgres allows robust concurrent scraping and easier backups.
- [ ] **Monitoring Dashboard**: A simple web UI (or Discord webhook) that reports:
    - Daily article count.
    - List of "Broken" scrapers.
    - VPS Memory/CPU usage.
- [ ] **Automated Tests**: specific tests for WAF detection logic to ensure we don't regress.

## Action Plan Checklist (Next 48 Hours)

1.  [ ] **Configure Docker Log Rotation** in `docker-compose.yml`.
2.  [ ] **Set up Discord Webhook** for daily health status reports.
3.  [ ] **Research Adelaide Bypass**: Test `curl_cffi` with `impersonate="chrome110"` vs `chrome124` vs `safari15_5`.
    *   **"Hash-Based" Skipping:** Store a content hash of the *latest* article. Scraper checks index page; if top item hash matches DB, stop scraping immediately. (Saves 90% of requests).

## 4. The Monitoring Phase (Q4 2026)
*   **Goal:** Passive monitoring.
*   **Dashboard:** A simple web view showing "Last Scrape Time" for every council.
*   **Alerting:** Discord/Email webhook when a council fails 5x in a row.

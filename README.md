# Council News Bot

Collects publicly published news from every Australian local council and
republishes it as attributed links on eight public Bluesky feeds — one per
state and territory.

**Live feeds, all in one place:** <https://lgnews.jonathonmarsden.com>
**About the crawler:** <https://lgnews.jonathonmarsden.com/bot.html>

[![Tests](https://github.com/jonathonmarsden/council-news-bot/actions/workflows/test.yml/badge.svg)](https://github.com/jonathonmarsden/council-news-bot/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11-blue)](requirements.txt)

---

## Why this exists

Most Australians never see news from their local council unless they go
looking for it. Road closures, grant rounds, meeting notices and community
programs are published across 500+ separate council websites that few
residents visit.

This project closes that gap. It reads each council's public news page once a
day and posts the headline, with a link back to the council's own site, to a
free public feed for that state. There is no paywall, no advertising, no
tracking, and no editorial curation. Every post sends readers to the council.

It is the companion data service to
[LG News Roundup](https://lgnewsroundup.com), Chris Eddy's local government
podcast, sponsored by the Victorian Local Governance Association.

**Coverage:** 534 of Australia's 537 local government areas.

## How it works

```
councils' news pages ──▶ collectors ──▶ PostgreSQL ──▶ paced queue ──▶ 8 Bluesky feeds
    (once daily)       (HTML/RSS/JSON)  (dedup by URL)  (<=18 posts/hr)
```

1. **Schedule** — councils are spread evenly across 24 hours so no shared
   platform ever sees a burst of requests.
2. **Collect** — per-council configuration selects a strategy (HTML selectors,
   RSS, or a public JSON endpoint) and extracts headline, link and date. A
   failing collector fails loudly and in isolation.
3. **Store** — every article is keyed by URL, which is what guarantees each
   story is published exactly once.
4. **Publish** — a paced queue posts to the state accounts well below platform
   rate limits, using an atomic claim so a crash can never double-post.

Councils are configuration, not code: adding one is a JSON entry in
`states/<state>/councils.json`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Design principles

- **Fail loudly.** A fetch failure and an empty page are different events and
  are recorded differently. Silent degradation is treated as the primary bug
  class, because it is the one that hides for months.
- **Exactly once.** Articles are claimed atomically before publishing.
- **Data minimisation.** Headline, URL, date, excerpt. Nothing else is
  collected or stored.
- **Polite by default.** One pass per council per day, capped retries, and an
  identifiable User-Agent for councils that ask for one.
- **Small attack surface.** No inbound network exposure, no accounts, no user
  input. See [SECURITY.md](SECURITY.md).

## Quick start

Requires Python 3.9+ and Docker (for PostgreSQL).

```bash
git clone https://github.com/jonathonmarsden/council-news-bot.git
cd council-news-bot
cp .env.example .env          # set DATABASE_URL; Bluesky credentials only if posting
pip install -r requirements.txt
docker compose up -d db
alembic upgrade head

# scrape a single council and print results without posting
python3 main.py --council ballarat --dry-run

# scrape one state, save to the database, post nothing
python3 main.py --state vic --scrape-only
```

Run the tests:

```bash
pytest tests/
```

## Repository layout

| Path | Contents |
|---|---|
| `main.py` | CLI entry point: scrape and publish pipeline |
| `core/scrapers/` | Collector strategies (HTML, RSS, JSON, browser, CMS-specific) |
| `core/` | Database models, publishing, validation, processing |
| `states/` | Per-state council configuration (JSON) |
| `scripts/` | Operations, monitoring and analysis tooling |
| `docs/` | Architecture, operations runbooks, and project reports |
| `tests/` | Test suite |

## Operating it

Production runs in containers on a small dedicated host, deployed by pulling
approved changes from `master`. Monitoring is quiet by default: it reports
only genuine problems, plus one daily digest, and an independent watchdog
checks the public feeds from outside the host so that total host failure is
still detected. See [docs/](docs/) for runbooks.

## For council web administrators

The crawler reads only your public news listing and links back to you. Full
details of what it requests and how often are published at
<https://lgnews.jonathonmarsden.com/bot.html>. If you would like it to use an
RSS feed or API instead, or have any question, email
**hello@jonathonmarsden.com** and it will be actioned promptly.

## Licence and contact

Apache-2.0 — see [LICENSE](LICENSE).

Built and maintained by Jonathon Marsden — software developer, former Mayor,
and postgraduate cyber security student. Contact:
**hello@jonathonmarsden.com**

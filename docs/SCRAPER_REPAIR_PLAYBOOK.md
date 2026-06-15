# Scraper Repair Playbook

How to find and fix silently-broken council scrapers. Distilled from a session
that restored 33 councils (2026-06-15). Start here before touching the long tail
in [`broken_councils.json`](broken_councils.json).

## The core insight

"Working" = scrapes valid, **dated**, recent articles **AND** those articles
reach the state BlueSky feed. A council can fail either half independently:

- **Scrapes fine but never posts** → queue/dedup/feed problem.
- **Posts historically but scraper now broken** → silent regression (the common case).

A feed posting twice daily can still have a third of its councils silently dead.
Per-council representation in recent posts is the signal that matters — not
whether the feed is "alive".

## Triage method (the lighter, high-signal variant)

1. **Feed representation.** Pull a deep author feed per state
   (`getAuthorFeed`, paginate ~800 posts), normalise council names, and tally
   which enabled councils actually appear. Match on BOTH the full name and a
   "short key" (strip Council/Shire/City of/Regional/the) — full-name-only
   matching produced false positives (e.g. "Sunshine Coast" posted but the
   matcher missed "Sunshine Coast Regional Council").
2. **Scrape only the absent councils** (not all 530) via
   `ScraperFactory.create_scraper(cfg).scrape()` with logging suppressed.
   Classify each: HEALTHY (valid+dated+recent) / STALE (valid but old) /
   JUNK (items but no valid dated articles) / DEAD (0 / error).
3. **Reconcile.** A council is only *confirmed broken* if it's **absent from a
   deep feed window AND scrapes JUNK/DEAD**. This step is essential — it rescued
   ~37 local-only false positives (sites that 403/Cloudflare-block the local IP
   but work in production).
4. **Confirm on the VPS** when in doubt. Running the same scrape inside the
   production bot container (`docker compose exec -T -w /app bot python3 ...`)
   splits "scraper logic broken" from "local network/IP blocked". In this
   session **all 62 reconciled-broken councils failed on the VPS too — zero
   false positives** — which validated the method.

### Gotchas that cost time
- Local scrape ≠ production: no rotating proxy, different IP. Trust the **feed**
  for "is it publishing"; use the VPS run to confirm scraper logic.
- The public BlueSky API can 502 during outages — fall back to profile URLs.
- 3 TAS test batches are excluded from CI (flaky live-WAF tests). Their failures
  are NOT regressions; CI ignores them. Verify with the same `--ignore` flags.
- Use the real current date for staleness math.
- `curl_cffi` with `impersonate` gets 200 where plain `curl` gets 403 — a plain
  403 usually means "needs impersonation", not "site down".

## Fix recipes (highest leverage first)

These are *cascades* — one diagnosis fixes many councils. Look for shared CMS
signatures before fixing one-by-one.

### 1. OpenCities (recovered 11 NSW councils)
Signature: `.list-item-container` / `.list-item-title` / `.published-on` (or
`.date`), classes like `page-name-news`, `listing-results`, `news-list-container`.
Two combined problems:
- **Wrong `news_url`** — configs often point at a *hub* page whose
  `.list-item-container`s are nav sub-links ("Latest news", "Subscribe"), not
  articles. Follow the site's "Latest news" / media-releases link to the real
  article-list URL.
- **JS-rendered** — use `browser_scraper` (Playwright), not curl.

Config:
```json
{ "scraper": "browser_scraper", "news_url": "<real article-list URL>",
  "item_selector": ".list-item-container", "title_selector": ".list-item-title",
  "link_selector": "a", "date_selector": ".published-on" }
```
Date selector varies by theme: `.published-on` on most, `.date` on Shoalhaven.
Duplicate items from the rendered grid are harmless (`articles.url` is UNIQUE).

### 2. Catalyst (newer JS variant) → `catalyst_browser_scraper` (recovered 3 WA)
Signature: `.newslisting` + `.pageTypeListing-results`, news loaded via an
`api/advancesearch` AJAX call (static HTML shows "0 results"). The classic
`catalyst_scraper` (static `.module-list .row`) sees nothing.
`CatalystBrowserScraper` renders with Playwright, reads each
`.pageTypeListing-results a[href]` whose text is "DD Month YYYY Title", and
splits the date off the title. Just set `"scraper": "catalyst_browser_scraper"`.
NOT all Catalyst sites match — Murray uses the *classic* `.module-list`/
`.module-item-wrapper` layout (would need a classic-layout browser variant).

### 3. Funnelback/Squiz redirect links → `opencities_scraper`
Signature: card links go through `funnelback.squiz.cloud/s/redirect?...url=...`.
`OpenCitiesScraper` already unwraps the `url=` param to the canonical URL
(Albury). Same engine the SA `lgasa_scraper` uses.

### 4. Dead/moved RSS → repoint the feed
ACT and West Daly: the configured RSS 404'd or went stale, but the council
publishes via a different live feed. Find it (CMTEDD media-releases for ACT,
`/feed/rss2` for West Daly's DudaOne site) and repoint `news_url`. **But** check
the feed actually carries `<pubDate>` — Denmark's RSS has none, so it can't pass
the staleness filter and isn't fixable this way.

### 5. WAF 403 → change impersonation
Tamworth 403'd on chrome but 200'd on `safari15_5`. Try
`"impersonate": "safari15_5"` (or chrome120) before assuming the site is gone.

### 6. Detail-page dates (CardScraper already supports this)
When the listing has no date but each article page does: set `date_selector` to
a detail-page element/meta. CardScraper auto-fetches detail pages when a
`date_selector` is set and reads `<meta>` content (e.g.
`meta[property='article:published_time']`). Used for Wagga, Irwin, Mount Marshall.

## Code-level fixes made this session (don't re-derive)
- `core/scrapers/base.py` `parse_date`: ISO-8601 (`YYYY-MM-DD...`) is now parsed
  WITHOUT `dayfirst` — passing `dayfirst=True` to an ISO string swaps day/month
  for days 1-12 (turned 12 June into 6 Dec). Bit Irwin and Moree.
- `core/validator.py` + `constants.py`: `is_valid_article` strips private-use-area
  glyphs (icon fonts) and rejects "read more" boilerplate titles.
- New scrapers in `core/scrapers/custom.py`: `NarromineScraper` (table layout,
  date glued in `span.label`), `MoreePlainsScraper` (Joomla blog, detail-page
  date), `CatalystBrowserScraper` (recipe #2).

## What's left and what NOT to bother with
- See [`broken_councils.json`](broken_councils.json) for the ~41 remaining, each
  with a per-council diagnosis.
- **Genuinely unfixable as-is** (don't sink time): PDF-only newsletter councils
  (NSW Hay, QLD Lockhart River/Richmond/Wujal Wujal), feeds with no dates
  (Denmark, Nambucca, Coonamble), councils that haven't published in 1-2 years.
- **`midcoast-council`**: selectors are correct but `fetch_page` returns None —
  a fetch-stack SSL/proxy bug, not a scraper problem. Fix the fetch layer.
- The cascade buckets (OpenCities, Catalyst) are exhausted. The rest are
  individual one-offs (JS-rendered, Squiz, Drupal) at ~1 council per several
  probes — batch them into a focused session, don't expect cascades.

## Verifying a fix
```bash
# Single council, no DB needed — this is how every fix was verified:
python3 -c "
import json, logging, sys, io; logging.disable(logging.CRITICAL)
from core.scrapers.factory import ScraperFactory
from core.validator import is_valid_article
c=next(x for x in json.load(open('states/<st>/councils.json'))['councils'] if x['id']=='<id>')
old=sys.stdout; sys.stdout=io.StringIO(); arts=ScraperFactory.create_scraper(c).scrape(); sys.stdout=old
v=[a for a in arts if is_valid_article(a)]; d=[a for a in v if a.date]
print(f'valid={len(v)} dated={len(d)} newest={max((a.date for a in d), default=None)}')
"
# Then: pytest (with the 3 TAS --ignore flags), commit, push -> CI auto-deploys.
# Recovery is proven by re-running the feed-representation triage after the next
# scrape window, NOT by the local scrape alone.
```

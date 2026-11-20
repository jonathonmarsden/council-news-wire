"""RSSScraper skips feed items whose link matches exclude_url_contains."""
from core.scrapers.rss import RSSScraper

FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Nominations closing soon</title>
<link>https://example.tas.gov.au/community-news/nominations-closing-soon/</link>
<pubDate>Thu, 19 Nov 2026 01:00:00 +0000</pubDate></item>
<item><title>Geoff Hill</title>
<link>https://example.tas.gov.au/councillors/geoff-hill/</link>
<pubDate>Thu, 19 Nov 2026 01:00:00 +0000</pubDate></item>
</channel></rss>"""


def _scrape(**kwargs):
    scraper = RSSScraper("west-coast", "West Coast Council", "https://example.tas.gov.au/feed/", **kwargs)
    scraper.fetch_page_or_raise = lambda url: FEED
    return scraper.scrape()


def test_excluded_paths_are_skipped():
    titles = [a.title for a in _scrape(exclude_url_contains=["/councillors/"])]
    assert titles == ["Nominations closing soon"]


def test_single_string_is_accepted():
    titles = [a.title for a in _scrape(exclude_url_contains="/councillors/")]
    assert titles == ["Nominations closing soon"]


def test_no_exclusion_keeps_everything():
    assert len(_scrape()) == 2

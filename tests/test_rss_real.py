"""
Live smoke tests for RSSScraper against real council feeds.

These are OPT-IN and excluded from the default suite: they depend on live
council websites, so they flake for reasons that have nothing to do with our
code (a feed is briefly down, a council has published nothing this week, the
runner's IP is WAF-blocked). Run them deliberately:

    pytest -m integration tests/test_rss_real.py

The default `pytest` run and CI skip them. Real correctness is covered by the
hermetic parsing tests in the regression suite.
"""
import os
import sys

import pytest

sys.path.append(os.getcwd())

from core.exceptions import ScrapeError
from core.scrapers.rss import RSSScraper

pytestmark = pytest.mark.integration

COUNCILS = [
    ("cootamundra-gundagai-regional-council", "https://www.cgrc.nsw.gov.au/feed/", "Cootamundra"),
    ("kyogle-council", "https://www.kyogle.nsw.gov.au/feed/", "Kyogle"),
    ("wentworth-shire-council", "https://www.wentworth.nsw.gov.au/feed/", "Wentworth"),
    ("cook", "https://www.cook.qld.gov.au/feed/", "Cook"),
    ("douglas", "https://douglas.qld.gov.au/feed/", "Douglas"),
    ("tablelands", "https://www.trc.qld.gov.au/feed/", "Tablelands"),
]


@pytest.mark.parametrize("council_id,url,name", COUNCILS, ids=[c[0] for c in COUNCILS])
def test_rss_feed_scrapes(council_id, url, name):
    scraper = RSSScraper(council_id, name, url)
    try:
        articles = scraper.scrape()
    except ScrapeError as e:
        pytest.skip(f"live feed unreachable from this network: {e}")

    # Fetch succeeded: the feed must parse into at least one sane article
    assert articles, f"{name}: feed fetched but parsed 0 articles"
    first = articles[0]
    assert first.title
    assert first.url.startswith("http")

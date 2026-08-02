"""Tests for reading a publication date from the article's own page.

Some councils print the date on the article but never on the listing that links
to it, so a listing scrape yields nothing. Denmark is the extreme case: its RSS
feed has no date field at all, yet every article page prints "30 July 2026" in
the body. 1,058 Denmark articles sat dateless for this reason.

The fallback is opt-in per council because it costs one extra HTTP request per
new article - worth it for the ~40 councils whose listings omit dates,
wasteful across the other 500.
"""
from datetime import datetime

import pytest

from core.scrapers.base import BaseScraper


class _Scraper(BaseScraper):
    """Serves canned HTML so the date logic can be tested without the network."""

    def __init__(self, page_html="", **kwargs):
        super().__init__("x", "X", "https://example.gov.au/news", **kwargs)
        self.page_html = page_html
        self.fetched = []

    def fetch_page(self, url):
        self.fetched.append(url)
        return self.page_html

    def scrape(self):  # pragma: no cover - not exercised
        return []


@pytest.mark.parametrize("html,expected", [
    ('<time datetime="2026-07-20T12:00:00Z">whenever</time>', (2026, 7, 20)),
    ('<meta property="article:published_time" content="2026-06-09">', (2026, 6, 9)),
    ('<div class="body"><p>Published 30 July 2026 by the Shire.</p></div>', (2026, 7, 30)),
])
def test_finds_date_by_each_route(html, expected):
    scraper = _Scraper(html, fetch_date_from_article=True)
    parsed = scraper.date_from_article_page("https://example.gov.au/news/story")
    assert parsed is not None
    assert (parsed.year, parsed.month, parsed.day) == expected
    assert parsed.tzinfo is None, "the DB column and freshness checks are naive"


def test_time_element_wins_over_body_text():
    """The body may mention other dates - an event date, a deadline.

    The machine-readable element is the article's own timestamp, so it takes
    precedence over anything found by scanning prose.
    """
    scraper = _Scraper(
        '<time datetime="2026-07-20">x</time>'
        '<p>Applications close 15 September 2026.</p>',
        fetch_date_from_article=True,
    )
    parsed = scraper.date_from_article_page("https://example.gov.au/news/story")
    assert (parsed.month, parsed.day) == (7, 20)


@pytest.mark.parametrize("html", [
    "<p>No date anywhere on this page.</p>",
    "<p>Copyright 2026 the Shire.</p>",          # bare year is not a date
    "<p>Read time: 3 min</p>",
    "",
])
def test_returns_none_rather_than_guessing(html):
    """A wrong date is worse than none.

    A fabricated near-now date pushes a stale story through the freshness
    filter; a fabricated old one buries a fresh story. Both are worse than
    leaving the field NULL, which the pipeline already tolerates.
    """
    scraper = _Scraper(html, fetch_date_from_article=True)
    assert scraper.date_from_article_page("https://example.gov.au/news/story") is None


def test_no_request_when_the_listing_already_supplied_a_date():
    """The extra fetch is a fallback, not a routine second lookup."""
    scraper = _Scraper('<time datetime="2026-01-01">x</time>',
                       fetch_date_from_article=True)
    article = scraper.create_article(
        "A story", "/news/story", date=datetime(2026, 7, 20))
    assert article.date == datetime(2026, 7, 20)
    assert scraper.fetched == [], "must not fetch when a date is already known"


def test_fallback_fills_a_missing_date():
    scraper = _Scraper('<time datetime="2026-07-20">x</time>',
                       fetch_date_from_article=True)
    article = scraper.create_article("A story", "/news/story")
    assert article.date is not None
    assert (article.date.month, article.date.day) == (7, 20)
    assert scraper.fetched == ["https://example.gov.au/news/story"], \
        "the article's own URL, not the listing's"


def test_disabled_by_default():
    """Off unless a council opts in, so 500 councils gain no extra requests."""
    scraper = _Scraper('<time datetime="2026-07-20">x</time>')
    article = scraper.create_article("A story", "/news/story")
    assert article.date is None
    assert scraper.fetched == []

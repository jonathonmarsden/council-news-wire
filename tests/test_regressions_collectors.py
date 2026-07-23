"""
Regression tests for collector defects (SCRAPE-1 .. SCRAPE-8, DATA-1).

The most consequential entry here is SCRAPE-1: because no collector ever
raised on a failed fetch, network and firewall failures were recorded as
"successful scrape, zero articles". That is the precise mechanism that
silently disabled 85 councils in June 2026.

All tests run offline: fetches are stubbed, never performed.
"""

from datetime import datetime, timedelta

import pytest

from core.exceptions import ScrapeError
from core.scrapers.base import BaseScraper
from core.scrapers.card import CardScraper
from core.scrapers.rss import RSSScraper


LISTING_HTML = """
<html><body>
  <div class="news-list">
    <article class="news-item">
      <h3><a href="/news/pool-hours">Pool opening hours change</a></h3>
      <span class="date">14 March 2026</span>
    </article>
    <article class="news-item">
      <h3><a href="/news/roadworks">Roadworks on Main Street</a></h3>
      <span class="date">12 March 2026</span>
    </article>
  </div>
</body></html>
"""


def card(monkeypatch, html, **cfg):
    """A CardScraper whose fetch is stubbed — no network."""
    s = CardScraper("testville", "Testville Shire Council",
                    "https://testville.gov.au/news", **cfg)
    monkeypatch.setattr(s, "fetch_page", lambda url: html)
    return s


class TestScrape1FetchFailureIsAFailureNotAnEmptyPage:
    """
    SCRAPE-1: a failed fetch returned None, which every collector converted to
    an empty list. The pipeline then recorded a *successful* run with zero
    articles, so the failure circuit breaker was unreachable dead code and
    outages were mistaken for councils that had simply published nothing.
    """

    def test_failed_fetch_raises_scrape_error(self, monkeypatch):
        s = card(monkeypatch, None)
        with pytest.raises(ScrapeError):
            s.scrape()

    def test_rss_failed_fetch_raises_scrape_error(self, monkeypatch):
        s = RSSScraper("testville", "Testville", "https://testville.gov.au/feed/")
        monkeypatch.setattr(s, "fetch_page", lambda url: None)
        with pytest.raises(ScrapeError):
            s.scrape()

    def test_successful_fetch_with_no_items_returns_empty_not_error(self, monkeypatch):
        """
        The other half of the contract: a page that genuinely lists nothing is
        an empty run, not a failure. Conflating the two is what broke the
        breaker in the first place.
        """
        s = card(monkeypatch, "<html><body><p>No news at present.</p></body></html>",
                 selectors={"item_selector": ".news-item"})
        assert s.scrape() == []


class TestScrape7SelectorMissDoesNotInventArticles:
    """
    SCRAPE-7: when a configured selector matched nothing, the collector swept
    every <a> on the page looking for news-ish links — publishing navigation
    menu entries as if they were articles, and hiding the fact that the
    council's markup had changed.
    """

    def test_configured_selector_that_matches_nothing_yields_nothing(self, monkeypatch):
        page = """
        <html><body>
          <nav><a href="/news/">News</a><a href="/news/archive">News archive</a></nav>
          <div class="content"><p>Our news page has moved.</p></div>
        </body></html>
        """
        s = card(monkeypatch, page, selectors={"item_selector": ".news-item"})
        assert s.scrape() == [], (
            "a configured selector that matches nothing must report nothing, "
            "not fall back to scraping navigation links"
        )

    def test_configured_selector_that_matches_returns_real_articles(self, monkeypatch):
        s = card(monkeypatch, LISTING_HTML, selectors={
            "item_selector": ".news-item",
            "title_selector": "h3 a",
            "link_selector": "h3 a",
            "date_selector": ".date",
        })
        articles = s.scrape()
        assert len(articles) == 2
        assert articles[0].title == "Pool opening hours change"
        assert articles[0].url.startswith("https://testville.gov.au/")


class TestScrape3AustralianDatesAreNotReadAmerican:
    """
    SCRAPE-3: eight call sites parsed dd/mm/yyyy as mm/dd/yyyy. Days 1-12
    silently produced wrong dates; days 13+ failed to parse and became None.
    """

    @pytest.mark.parametrize("text,expected", [
        ("05/06/2026", (2026, 6, 5)),      # 5 June, not 6 May
        ("12/06/2026", (2026, 6, 12)),     # 12 June, not 6 December
        ("14 March 2026", (2026, 3, 14)),
        ("2026-06-05", (2026, 6, 5)),      # ISO must not be flipped by dayfirst
    ])
    def test_dates_parse_as_australian(self, text, expected):
        parsed = _parse(text)
        assert parsed is not None, f"{text!r} should parse"
        assert (parsed.year, parsed.month, parsed.day) == expected


class TestScrape2JunkDoesNotBecomeAFreshDate:
    """
    SCRAPE-2: the fuzzy date parser filled missing components from *today*, so
    a misconfigured selector picking up "3 min read" produced a near-now date.
    Those articles then passed the freshness filter and were published as new.
    """

    @pytest.mark.parametrize("junk", [
        "3 min read", "Read more", "Share this page", "", "   ", "2026",
    ])
    def test_junk_text_yields_no_date(self, junk):
        assert _parse(junk) is None, (
            f"{junk!r} must not be interpreted as a date"
        )

    def test_relative_dates_are_understood(self):
        today = _parse("today")
        assert today is not None and today.date() == datetime.now().date()

        two_days = _parse("2 days ago")
        assert two_days is not None
        assert (datetime.now() - two_days).days == 2

    def test_month_and_year_is_accepted_for_newsletters(self):
        """PDF newsletter titles legitimately carry only month and year."""
        d = _parse("Waanta Newsletter October 2025")
        assert d is not None and (d.year, d.month) == (2025, 10)


class TestData1EncodingIsFixedAtIngest:
    """
    DATA-1: pages served without a charset were decoded as ISO-8859-1, turning
    UTF-8 punctuation into mojibake that was then stored and published.
    """

    def test_missing_charset_header_decodes_as_utf8(self):
        class Resp:
            headers = {"content-type": "text/html"}     # no charset
            encoding = "ISO-8859-1"
            apparent_encoding = "utf-8"
            text = "Council’s new plan"

        decoded = BaseScraper._decode_response(Resp())
        assert "’" in decoded and "â€™" not in decoded

    def test_declared_charset_is_respected(self):
        class Resp:
            headers = {"content-type": "text/html; charset=utf-8"}
            encoding = "utf-8"
            apparent_encoding = "utf-8"
            text = "Council’s new plan"

        assert BaseScraper._decode_response(Resp()) == "Council’s new plan"


class TestScrape6MissingContentIsNotPublishedAsText:
    """
    SCRAPE-6: when an optional content selector matched nothing, the collector
    stringified the missing element and published the literal text "None" as
    the article excerpt.
    """

    def test_absent_optional_selector_does_not_produce_none_excerpt(self, monkeypatch):
        s = card(monkeypatch, LISTING_HTML, selectors={
            "item_selector": ".news-item",
            "title_selector": "h3 a",
            "link_selector": "h3 a",
        })
        for a in s.scrape():
            assert a.excerpt != "None", "the string 'None' must never be an excerpt"


def _parse(text):
    """Parse via a real scraper instance (parse_date is an instance method)."""
    s = CardScraper("t", "T", "https://example.gov.au/news")
    return s.parse_date(text)

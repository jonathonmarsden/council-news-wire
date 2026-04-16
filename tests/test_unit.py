"""
Fixture-based unit tests for core modules.

All tests use mocks/fixtures — no live network calls, no database required.
"""

from __future__ import annotations

from datetime import datetime
from typing import List
from unittest.mock import MagicMock, patch, call

import pytest

from core.scrapers.base import BaseScraper, NewsArticle
from core.scrapers.card import CardScraper
from core.validator import is_valid_article, validate_post
from core.processing import process_articles


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def make_article():
    """Factory fixture that returns NewsArticle instances."""
    def _make(title="Council News Update", url="https://example.com/news/1",
              date=None, excerpt="A summary."):
        return NewsArticle(
            council_id="test-council",
            council_name="Test Council",
            title=title,
            url=url,
            date=date or datetime(2026, 4, 10),
            excerpt=excerpt,
        )
    return _make


@pytest.fixture
def make_db():
    """Return a MagicMock that satisfies the Database interface used by processing."""
    db = MagicMock()
    db.add_articles_bulk.return_value = 1
    db.get_unposted_articles.return_value = []
    return db


@pytest.fixture
def card_scraper():
    return CardScraper(
        council_id="test",
        council_name="Test Council",
        news_url="https://example.com/news",
    )


# ---------------------------------------------------------------------------
# is_valid_article
# ---------------------------------------------------------------------------

class TestIsValidArticle:
    def test_valid_article_object(self, make_article):
        assert is_valid_article(make_article()) is True

    def test_valid_article_dict(self):
        assert is_valid_article({"title": "Council approves new park"}) is True

    def test_empty_title(self):
        assert is_valid_article({"title": ""}) is False

    def test_none_title(self):
        assert is_valid_article({"title": None}) is False

    def test_too_short(self):
        assert is_valid_article({"title": "Hi"}) is False

    def test_purely_numeric(self):
        assert is_valid_article({"title": "2026"}) is False
        assert is_valid_article({"title": "6175"}) is False

    def test_generic_navigation(self):
        assert is_valid_article({"title": "News"}) is False
        assert is_valid_article({"title": "Home"}) is False
        assert is_valid_article({"title": "Contact Us"}) is False

    def test_address_like(self):
        assert is_valid_article({"title": "1 Smith Street redevelopment"}) is False

    def test_metadata_title(self):
        assert is_valid_article({"title": "Posted 04 December 2025"}) is False

    def test_copyright_footer(self):
        assert is_valid_article({"title": "© 2025 Shire of Example"}) is False

    def test_garbage_title(self):
        assert is_valid_article({"title": "Array"}) is False
        assert is_valid_article({"title": "No Title"}) is False

    def test_case_insensitive_generic(self):
        assert is_valid_article({"title": "NEWS"}) is False

    def test_legitimate_news(self):
        assert is_valid_article({"title": "Mayor announces new community garden"}) is True
        assert is_valid_article({"title": "Roads closed for maintenance works"}) is True


# ---------------------------------------------------------------------------
# validate_post
# ---------------------------------------------------------------------------

class TestValidatePost:
    def _facets(self, text, spans):
        """Helper: encode text and return facets for given substring spans."""
        return [(text.encode().index(s.encode()), text.encode().index(s.encode()) + len(s.encode()))
                for s in spans]

    def test_valid_post(self):
        text = "Test title\n#LGNewsRoundup #VicCouncils #BallCity"
        errors = validate_post(
            text=text,
            title="Test title",
            excerpt=None,
            url="https://example.com/article",
            hashtags=["#LGNewsRoundup", "#VicCouncils", "#BallCity"],
            facets=[],
        )
        assert errors == []

    def test_title_too_short(self):
        errors = validate_post("Hi", "Hi", None, "https://x.com/a",
                               ["#A", "#B", "#C"], [])
        assert any("short" in e.lower() for e in errors)

    def test_title_too_long(self):
        long_title = "x" * 300
        errors = validate_post(long_title, long_title, None, "https://x.com/a",
                               ["#A", "#B", "#C"], [])
        assert any("long" in e.lower() for e in errors)

    def test_excerpt_contains_url(self):
        errors = validate_post("T", "T" * 10, "See https://spam.com",
                               "https://x.com/a", ["#A", "#B", "#C"], [])
        assert any("excerpt" in e.lower() for e in errors)

    def test_invalid_url(self):
        errors = validate_post("T", "Valid title", None, "ftp://bad.url",
                               ["#A", "#B", "#C"], [])
        assert any("url" in e.lower() for e in errors)

    def test_missing_hashtags(self):
        errors = validate_post("T", "Valid title", None, "https://x.com/a",
                               [], [])
        assert any("hashtag" in e.lower() for e in errors)

    def test_facet_out_of_range(self):
        text = "Hello"
        errors = validate_post(text, "Valid title", None, "https://x.com/a",
                               ["#A", "#B", "#C"], [(0, 999)])
        assert any("facet" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# BaseScraper._retry
# ---------------------------------------------------------------------------

class TestRetry:
    def test_succeeds_on_first_attempt(self, card_scraper):
        fn = MagicMock(return_value="<html>content</html>")
        result = card_scraper._retry(fn, max_attempts=3, base_delay=0)
        assert result == "<html>content</html>"
        assert fn.call_count == 1

    def test_retries_on_none(self, card_scraper):
        fn = MagicMock(side_effect=[None, None, "<html>ok</html>"])
        result = card_scraper._retry(fn, max_attempts=3, base_delay=0)
        assert result == "<html>ok</html>"
        assert fn.call_count == 3

    def test_returns_none_after_all_attempts(self, card_scraper):
        fn = MagicMock(return_value=None)
        result = card_scraper._retry(fn, max_attempts=3, base_delay=0)
        assert result is None
        assert fn.call_count == 3

    def test_handles_exception(self, card_scraper):
        fn = MagicMock(side_effect=[Exception("network error"), "<html>ok</html>"])
        result = card_scraper._retry(fn, max_attempts=3, base_delay=0)
        assert result == "<html>ok</html>"
        assert fn.call_count == 2

    def test_all_exceptions_returns_none(self, card_scraper):
        fn = MagicMock(side_effect=Exception("always fails"))
        result = card_scraper._retry(fn, max_attempts=3, base_delay=0)
        assert result is None
        assert fn.call_count == 3


# ---------------------------------------------------------------------------
# process_articles (mocked DB)
# ---------------------------------------------------------------------------

class TestProcessArticles:
    def test_fresh_articles_queued(self, make_article, make_db):
        articles = [make_article(date=datetime(2026, 4, 15))]
        make_db.get_unposted_articles.return_value = [{"title": "Council News Update"}]

        result = process_articles(articles, make_db, "VIC")

        make_db.add_articles_bulk.assert_called()
        # Fresh article should go to 'new' bucket
        first_call_args = make_db.add_articles_bulk.call_args_list[0]
        assert first_call_args[1].get('status') == 'new' or first_call_args[0][2] == 'new'
        assert result == [{"title": "Council News Update"}]

    def test_old_articles_archived(self, make_article, make_db):
        old_date = datetime(2020, 1, 1)
        articles = [make_article(date=old_date)]

        process_articles(articles, make_db, "VIC")

        # Second bulk call should be the archived batch
        calls = make_db.add_articles_bulk.call_args_list
        statuses = [c[1].get('status') or c[0][2] for c in calls]
        assert 'archived' in statuses

    def test_garbage_articles_rejected(self, make_db):
        garbage = [
            NewsArticle("c", "C", "Array", "https://x.com/1", datetime(2026, 4, 15)),
            NewsArticle("c", "C", "2026", "https://x.com/2", datetime(2026, 4, 15)),
        ]
        process_articles(garbage, make_db, "VIC")
        # No articles should reach the DB
        for c in make_db.add_articles_bulk.call_args_list:
            data = c[0][0]
            assert data == [], f"Expected empty batch but got: {data}"

    def test_force_fresh_bypasses_age_filter(self, make_article, make_db):
        old_article = make_article(date=datetime(2020, 1, 1))
        process_articles([old_article], make_db, "VIC", force_fresh=True)

        first_call = make_db.add_articles_bulk.call_args_list[0]
        status = first_call[1].get('status') or first_call[0][2]
        assert status == 'new'

    def test_empty_input(self, make_db):
        result = process_articles([], make_db, "VIC")
        assert result == make_db.get_unposted_articles.return_value


# ---------------------------------------------------------------------------
# CardScraper.fetch_page (mocked — no live HTTP)
# ---------------------------------------------------------------------------

class TestCardScraperFetch:
    def test_uses_requests_by_default(self, card_scraper):
        with patch.object(card_scraper, '_fetch_with_requests', return_value="<html/>") as mock_fetch:
            result = card_scraper.fetch_page("https://example.com/news")
        mock_fetch.assert_called_once_with("https://example.com/news")
        assert result == "<html/>"

    def test_uses_curl_when_configured(self):
        scraper = CardScraper("c", "C", "https://example.com", use_curl=True)
        with patch.object(scraper, '_fetch_with_curl', return_value="<html/>") as mock_curl:
            result = scraper.fetch_page("https://example.com/news")
        mock_curl.assert_called_once()
        assert result == "<html/>"

"""Tests for widening the seven-day freshness window after an outage.

After the 29 Oct to 1 Nov 2026 host outage, stories published on day one
of the gap were seven days old by the time the bot caught up and were
archived on arrival (Prospect's 15 October story arrived on day seven and
was never posted). MAX_ARTICLE_AGE_DAYS in the environment, or
--max-age-days on main.py, widens the window for a catch-up run and covers
both the scrape path and the queue path without a restart.
"""
from datetime import datetime, timedelta

import pytest

from core.models import Article
from core.processing import process_articles
from core.scrapers.base import NewsArticle
from core.utils import max_article_age_days


@pytest.mark.parametrize("raw,expected", [
    (None, 7), ("", 7), ("10", 10), ("abc", 7), ("0", 7), ("-3", 7), (" 14 ", 14),
])
def test_helper_reads_the_environment_defensively(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("MAX_ARTICLE_AGE_DAYS", raising=False)
    else:
        monkeypatch.setenv("MAX_ARTICLE_AGE_DAYS", raw)
    assert max_article_age_days() == expected


def _queue(db, url, days_old):
    db.add_articles_bulk([{
        "url": url, "council_id": "prospect", "title": "Prospect Road businesses recognised",
        "date": datetime.now() - timedelta(days=days_old), "excerpt": "x",
    }], "SA")


def _status(db, url):
    with db.get_session() as s:
        return s.query(Article).filter(Article.url == url).one().status


def test_queue_keeps_a_nine_day_old_story_when_the_window_is_ten(db, monkeypatch):
    monkeypatch.setenv("MAX_ARTICLE_AGE_DAYS", "10")
    url = "https://prospect.sa.gov.au/news/businesses"
    _queue(db, url, 9)
    assert [a["url"] for a in db.get_unposted_articles("SA")] == [url]


def test_queue_still_suppresses_at_nine_days_by_default(db, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLE_AGE_DAYS", raising=False)
    url = "https://prospect.sa.gov.au/news/businesses"
    _queue(db, url, 9)
    assert db.get_unposted_articles("SA") == []
    assert _status(db, url) == "suppressed_too_old"


def _scraped(days_old):
    return NewsArticle(council_id="prospect", council_name="City of Prospect",
                       title="Prospect Road businesses recognised in inaugural awards",
                       url="https://prospect.sa.gov.au/news/awards",
                       date=datetime.now() - timedelta(days=days_old), excerpt="A real summary of the awards night.")


def test_scrape_path_archives_on_arrival_by_default(db, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLE_AGE_DAYS", raising=False)
    process_articles([_scraped(9)], db, "SA")
    assert _status(db, "https://prospect.sa.gov.au/news/awards") == "archived"


def test_scrape_path_keeps_the_story_when_the_window_is_widened(db, monkeypatch):
    monkeypatch.setenv("MAX_ARTICLE_AGE_DAYS", "10")
    process_articles([_scraped(9)], db, "SA")
    assert _status(db, "https://prospect.sa.gov.au/news/awards") == "new"


def test_window_is_read_at_call_time_not_import_time(db, monkeypatch):
    url = "https://prospect.sa.gov.au/news/businesses"
    _queue(db, url, 9)
    monkeypatch.setenv("MAX_ARTICLE_AGE_DAYS", "10")
    assert len(db.get_unposted_articles("SA")) == 1

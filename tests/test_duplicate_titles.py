"""Tests for title-based duplicate suppression.

URL matching alone let councils re-issue the same story at a new URL: one ACT
headline appeared four times, another twice a fortnight apart. Roughly 0.6% of
posts in a week were repeats. These tests pin the guard and, just as
importantly, the cases it must NOT suppress.
"""
from datetime import datetime, timedelta

import pytest

from core.database import Database
from core.models import Article


def add(db, url, title, council="testville", date=None):
    return db.add_articles_bulk([{
        "url": url, "council_id": council, "title": title,
        "date": date or datetime.now(), "excerpt": "e",
    }], "VIC")


def count(db):
    with db.get_session() as s:
        return s.query(Article).count()


def test_same_title_new_url_is_suppressed(db):
    """The actual failure: a council republishes a notice at a fresh URL."""
    assert add(db, "https://x.gov.au/news/1", "Get ready for the 2026 school year") == 1
    assert add(db, "https://x.gov.au/news/2", "Get ready for the 2026 school year") == 0
    assert count(db) == 1


def test_same_url_still_suppressed(db):
    """The original URL guard must keep working."""
    assert add(db, "https://x.gov.au/news/1", "Pool opening hours change") == 1
    assert add(db, "https://x.gov.au/news/1", "Pool opening hours change") == 0


def test_different_councils_may_share_a_title(db):
    """'Parks Maintenance Works' is not one council's property."""
    assert add(db, "https://a.gov.au/n/1", "Parks Maintenance Works", council="alpha") == 1
    assert add(db, "https://b.gov.au/n/1", "Parks Maintenance Works", council="bravo") == 1
    assert count(db) == 2


def test_different_titles_from_one_council_both_kept(db):
    assert add(db, "https://x.gov.au/n/1", "Council adopts the 2026 budget") == 1
    assert add(db, "https://x.gov.au/n/2", "Library opening hours this winter") == 1
    assert count(db) == 2


def test_title_match_ignores_case_and_whitespace(db):
    assert add(db, "https://x.gov.au/n/1", "Council Adopts The Budget Tonight") == 1
    assert add(db, "https://x.gov.au/n/2", "  council adopts the budget tonight ") == 0


def test_very_short_titles_are_not_matched(db):
    """Too generic to suppress on safely - better a rare duplicate than a loss."""
    assert add(db, "https://x.gov.au/n/1", "Notice") == 1
    assert add(db, "https://x.gov.au/n/2", "Notice") == 1


def test_an_old_repeat_is_allowed_again(db):
    """An annual notice should publish next year, not be silently dropped."""
    add(db, "https://x.gov.au/n/1", "Get ready for the school year")
    with db.get_session() as s:
        art = s.query(Article).one()
        art.first_seen_at = datetime.now() - timedelta(
            days=Database.DUPLICATE_TITLE_WINDOW_DAYS + 5)
        s.commit()
    assert add(db, "https://x.gov.au/n/2", "Get ready for the school year") == 1
    assert count(db) == 2


def test_missing_title_or_council_does_not_crash(db):
    with db.get_session() as s:
        assert db._recent_duplicate_title(s, None, "testville") is False
        assert db._recent_duplicate_title(s, "A title long enough", None) is False

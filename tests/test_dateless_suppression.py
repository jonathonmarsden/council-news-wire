"""Tests for giving a dateless article the same shelf life as a dated one.

The 7-day freshness check reads `if suppress_stale and o.date`, so an article
with no date was never too old. It stayed eligible forever and surfaced
whenever the fresh queue ran dry: on 1 Nov 2026, after a three-day outage,
the SA feed posted seven undated City of Marion stories in fifty minutes,
including a Father's Day piece (6 Sept) and a Christmas-lights one. The day
we first saw an article is the best date we have for it.
"""
from datetime import datetime, timedelta

from core.models import Article


def _queue(db, url, title, date):
    db.add_articles_bulk([{
        "url": url, "council_id": "marion", "title": title, "date": date, "excerpt": "x",
    }], "SA")


def _first_seen(db, url, days_ago):
    with db.get_session() as s:
        a = s.query(Article).filter(Article.url == url).one()
        a.first_seen_at = datetime.now() - timedelta(days=days_ago)
        s.commit()


def _status(db, url):
    with db.get_session() as s:
        return s.query(Article).filter(Article.url == url).one().status


def test_old_dateless_article_is_suppressed(db):
    url = "https://marion.sa.gov.au/news/fathers-day-fun"
    _queue(db, url, "Father's Day fun for every kind of dad", None)
    _first_seen(db, url, 56)

    assert db.get_unposted_articles("SA") == []
    assert _status(db, url) == "suppressed_too_old"


def test_fresh_dateless_article_still_posts(db):
    url = "https://marion.sa.gov.au/news/woofstock"
    _queue(db, url, "Woofstock returns to Marion", None)
    _first_seen(db, url, 2)

    assert [a["url"] for a in db.get_unposted_articles("SA")] == [url]
    assert _status(db, url) == "new"


def test_dateless_article_seen_just_inside_the_window_is_kept(db):
    url = "https://marion.sa.gov.au/news/trails"
    _queue(db, url, "Discover our stunning trails", None)
    _first_seen(db, url, 6)

    assert len(db.get_unposted_articles("SA")) == 1


def test_dated_articles_are_judged_by_their_date_not_discovery(db):
    # Seen long ago but dated this week (a late-added date): still fresh.
    url = "https://marion.sa.gov.au/news/late-dated"
    _queue(db, url, "Late dated story", datetime.now())
    _first_seen(db, url, 30)
    assert len(db.get_unposted_articles("SA")) == 1

    # Seen today but dated two months ago: stale, as before.
    old = "https://marion.sa.gov.au/news/old-dated"
    _queue(db, old, "Old dated story", datetime.now() - timedelta(days=60))
    assert [a["url"] for a in db.get_unposted_articles("SA")] == [url]
    assert _status(db, old) == "suppressed_too_old"


def test_force_fresh_bypasses_the_dateless_check_too(db):
    url = "https://marion.sa.gov.au/news/forced"
    _queue(db, url, "Forced out", None)
    _first_seen(db, url, 40)
    assert len(db.get_unposted_articles("SA", suppress_stale=False)) == 1

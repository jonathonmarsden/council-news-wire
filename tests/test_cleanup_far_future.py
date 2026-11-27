"""The monthly cleanup archives only unposted rows dated implausibly far ahead.

It once compared against the literal '2027-01-01', which from January 2027
would have archived every current story and stamped each as posted today.
"""
from datetime import datetime, timedelta

from sqlalchemy import text

from scripts.maintenance.cleanup_remote_db import (
    FAR_FUTURE_DAYS, archive_far_future, far_future_cutoff)


def _rows(db):
    with db.get_session() as s:
        return {r.url: (r.status, r.posted_at) for r in s.execute(
            text("SELECT url, status, posted_at FROM articles"))}


def test_cutoff_moves_with_the_calendar():
    now = datetime(2027, 2, 1)
    assert far_future_cutoff(now) == now + timedelta(days=FAR_FUTURE_DAYS)
    assert far_future_cutoff(now) > datetime(2027, 12, 31)


def test_only_unposted_far_future_rows_are_archived(db):
    now = datetime.now()
    db.add_articles_bulk([
        {"url": "https://x.gov.au/today", "council_id": "c", "title": "A story from today",
         "date": now, "excerpt": ""},
        {"url": "https://x.gov.au/next-month", "council_id": "c", "title": "An event next month",
         "date": now + timedelta(days=30), "excerpt": ""},
        {"url": "https://x.gov.au/garbage", "council_id": "c", "title": "A mis-parsed date",
         "date": now + timedelta(days=900), "excerpt": ""},
        {"url": "https://x.gov.au/posted", "council_id": "c", "title": "Already posted, odd date",
         "date": now + timedelta(days=900), "excerpt": ""},
    ], "VIC")
    stamp = datetime(2026, 5, 1, 9, 0, 0)
    with db.get_session() as s:
        s.execute(text("UPDATE articles SET status='posted', posted_at=:t WHERE url LIKE '%/posted'"),
                  {"t": stamp})
        s.commit()

    with db.get_session() as s:
        assert archive_far_future(s) == 1
        s.commit()

    rows = _rows(db)
    assert rows["https://x.gov.au/today"][0] == "new"
    assert rows["https://x.gov.au/next-month"][0] == "new"
    assert rows["https://x.gov.au/garbage"] == ("archived", None)
    status, posted_at = rows["https://x.gov.au/posted"]
    assert status == "posted"
    assert str(posted_at).startswith("2026-05-01 09:00:00")

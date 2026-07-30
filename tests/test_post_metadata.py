"""Tests for persisting where and how an article was published.

Before these columns existed the system recorded THAT an article was posted but
not WHERE, so finding a story's own post meant scraping the public feed and
matching on title - which is how a duplicate slipped through a card backfill.
"""
from datetime import datetime

import pytest

from core.models import Article
from core.processing import post_articles


COUNCILS = {"testville": {"name": "Testville Shire Council"}}


def queue_one(db, url="https://testville.gov.au/news/1"):
    db.add_articles_bulk([{
        "url": url, "council_id": "testville", "title": "Pool hours change",
        "date": datetime.now(), "excerpt": "Summer hours start Monday.",
    }], "VIC")
    return db.get_unposted_articles("VIC")


def stored(db, url="https://testville.gov.au/news/1"):
    with db.get_session() as s:
        return s.query(Article).filter(Article.url == url).one()


def test_bluesky_uri_is_persisted_on_post(db, poster):
    articles = queue_one(db)
    p = poster()
    post_articles(articles, p, db, COUNCILS, ["#LGNewsRoundup"], {})
    art = stored(db)
    assert art.status == "posted"
    assert art.bluesky_uri, "the post's own URI must be recorded"
    assert art.bluesky_uri.startswith("at://")


def test_mark_as_posted_accepts_no_metadata(db):
    """Older callers pass nothing; behaviour must be unchanged."""
    url = "https://testville.gov.au/news/2"
    db.add_articles_bulk([{
        "url": url, "council_id": "testville", "title": "T",
        "date": datetime.now(), "excerpt": "e",
    }], "VIC")
    db.mark_as_posted(url, "roundupnewsbotvic.bsky.social")
    art = stored(db, url)
    assert art.status == "posted" and art.posted_at is not None
    assert art.bluesky_uri is None


def test_mark_as_posted_writes_og_and_image_status(db):
    url = "https://testville.gov.au/news/3"
    db.add_articles_bulk([{
        "url": url, "council_id": "testville", "title": "T",
        "date": datetime.now(), "excerpt": "e",
    }], "VIC")
    db.mark_as_posted(url, "handle", {
        "bluesky_uri": "at://did:plc:x/app.bsky.feed.post/abc",
        "bluesky_cid": "bafy123",
        "og_image_url": "https://testville.gov.au/img.jpg",
        "og_description": "A summary",
        "image_status": "image",
    })
    art = stored(db, url)
    assert art.bluesky_uri.endswith("/abc")
    assert art.bluesky_cid == "bafy123"
    assert art.og_image_url.endswith("img.jpg")
    assert art.og_description == "A summary"
    assert art.image_status == "image"


def test_unknown_metadata_keys_are_ignored(db):
    """A caller passing junk must not blow up the update."""
    url = "https://testville.gov.au/news/4"
    db.add_articles_bulk([{
        "url": url, "council_id": "testville", "title": "T",
        "date": datetime.now(), "excerpt": "e",
    }], "VIC")
    db.mark_as_posted(url, "handle", {"bluesky_uri": "at://a/b/c", "nonsense": "x"})
    assert stored(db, url).bluesky_uri == "at://a/b/c"


def test_image_status_none_when_cards_disabled(db, poster, monkeypatch):
    """With link cards off there is no OG fetch, so status records 'none'."""
    monkeypatch.delenv("LINK_CARDS_STATES", raising=False)
    articles = queue_one(db, "https://testville.gov.au/news/5")
    p = poster()
    post_articles(articles, p, db, COUNCILS, ["#LGNewsRoundup"], {})
    art = stored(db, "https://testville.gov.au/news/5")
    assert art.image_status == "none"
    assert art.og_image_url is None

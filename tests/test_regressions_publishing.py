"""
Regression tests for publishing defects (POST-1 .. POST-4).

Each test corresponds to a defect found in the July 2026 review and named in
docs/CODE_REVIEW_2026-07-07.md. They exist to prove those specific failures
cannot return. All run offline against a fake client.
"""

from datetime import datetime

import pytest

from core.database import Database
from core.exceptions import TransientPostError
from core.processing import post_articles
from tests.conftest import FakeHTTPError


COUNCILS = {"testville": {"name": "Testville Shire Council"}}


def queued(db, url="https://testville.gov.au/news/1"):
    """Insert one fresh article and return the queue as post_articles wants it."""
    db.add_articles_bulk([{
        "url": url, "council_id": "testville", "title": "Pool opening hours change",
        "date": datetime.now(), "excerpt": "Summer hours start Monday.",
    }], "VIC")
    return db.get_unposted_articles("VIC")


class TestPost1TransientFailuresDoNotDestroyArticles:
    """
    POST-1: a transient BlueSky failure (429/5xx/timeout/auth) used to be
    indistinguishable from a validation rejection, so the article was marked
    permanently rejected and never retried. An outage silently destroyed
    every article attempted during it.
    """

    @pytest.mark.parametrize("status", [429, 500, 502, 503, 408])
    def test_transient_http_errors_leave_article_queued(self, db, poster, status):
        articles = queued(db)
        p = poster(fail_with=FakeHTTPError(status), fail_times=-1)

        post_articles(articles, p, db, COUNCILS, ["#LGNewsRoundup"], {})

        still_queued = db.get_unposted_articles("VIC")
        assert len(still_queued) == 1, (
            f"HTTP {status} must leave the article queued for retry, not discard it"
        )
        assert p.client.posts == []

    def test_network_error_leaves_article_queued(self, db, poster):
        articles = queued(db)
        p = poster(fail_with=ConnectionError("connection reset"), fail_times=-1)

        post_articles(articles, p, db, COUNCILS, ["#LGNewsRoundup"], {})

        assert len(db.get_unposted_articles("VIC")) == 1

    def test_authentication_failure_raises_transient_not_silent_loss(self, poster):
        p = poster(auth_fails=True)

        with pytest.raises(TransientPostError):
            p.post_article("Testville Shire Council", "A title",
                           "https://testville.gov.au/news/1")

    def test_permanent_api_rejection_returns_none_not_exception(self, db, poster):
        """A genuine 400 (malformed record) is permanent: reject, don't retry forever."""
        p = poster(fail_with=FakeHTTPError(400), fail_times=-1)
        result = p.post_article("Testville Shire Council", "A title",
                                "https://testville.gov.au/news/1")
        assert result is None


class TestPost1DeadLetter:
    """
    POST-1 (cap): repeated transient failures must eventually dead-letter,
    so a poison article cannot be retried forever.
    """

    def test_article_dead_letters_after_max_attempts(self, db):
        url = "https://testville.gov.au/news/poison"
        db.add_articles_bulk([{
            "url": url, "council_id": "testville", "title": "Poison",
            "date": datetime.now(), "excerpt": "x",
        }], "VIC")

        dead = False
        for _ in range(Database.MAX_POST_ATTEMPTS):
            db.claim_article(url)
            dead = db.release_claim(url)

        assert dead is True
        assert db.get_unposted_articles("VIC") == [], (
            "dead-lettered articles must leave the queue"
        )


class TestPost2ExactlyOncePublishing:
    """
    POST-2/3: two uncoordinated posting processes could publish the same
    article twice, and a crash between send and database update could
    republish on the next run. Publishing now claims atomically first.
    """

    def test_claim_is_exclusive(self, db):
        url = "https://testville.gov.au/news/1"
        db.add_articles_bulk([{
            "url": url, "council_id": "testville", "title": "T",
            "date": datetime.now(), "excerpt": "e",
        }], "VIC")

        assert db.claim_article(url) is True, "first claimant wins"
        assert db.claim_article(url) is False, "second claimant must be refused"

    def test_claimed_article_is_invisible_to_other_readers(self, db):
        url = "https://testville.gov.au/news/1"
        db.add_articles_bulk([{
            "url": url, "council_id": "testville", "title": "T",
            "date": datetime.now(), "excerpt": "e",
        }], "VIC")
        db.claim_article(url)

        assert db.get_unposted_articles("VIC") == [], (
            "a claimed article must not be handed to a concurrent process"
        )

    def test_released_claim_returns_to_queue(self, db):
        url = "https://testville.gov.au/news/1"
        db.add_articles_bulk([{
            "url": url, "council_id": "testville", "title": "T",
            "date": datetime.now(), "excerpt": "e",
        }], "VIC")
        db.claim_article(url)
        db.release_claim(url)

        assert len(db.get_unposted_articles("VIC")) == 1

    def test_successful_post_publishes_exactly_once(self, db, poster):
        articles = queued(db)
        p = poster()

        post_articles(articles, p, db, COUNCILS, ["#LGNewsRoundup"], {})

        assert len(p.client.posts) == 1
        assert db.get_unposted_articles("VIC") == []

    def test_rerunning_does_not_republish(self, db, poster):
        """The defining property: run the queue twice, publish once."""
        p = poster()
        post_articles(queued(db), p, db, COUNCILS, ["#LGNewsRoundup"], {})
        post_articles(db.get_unposted_articles("VIC"), p, db, COUNCILS,
                      ["#LGNewsRoundup"], {})

        assert len(p.client.posts) == 1


class TestPost4StatusLifecycle:
    """
    QUAL-4: posted articles were left at status 'new' forever, and rejections
    were recorded as posts — corrupting every statistic derived from them.
    """

    def test_posted_article_has_posted_status(self, db, poster):
        articles = queued(db)
        post_articles(articles, poster(), db, COUNCILS, ["#LGNewsRoundup"], {})

        with db.get_session() as s:
            from core.models import Article
            art = s.query(Article).one()
            assert art.status == "posted"
            assert art.posted_at is not None

    def test_rejection_is_not_counted_as_a_post(self, db):
        url = "https://testville.gov.au/news/1"
        db.add_articles_bulk([{
            "url": url, "council_id": "testville", "title": "T",
            "date": datetime.now(), "excerpt": "e",
        }], "VIC")
        db.mark_as_rejected(url, "REJECTED_VALIDATION")

        with db.get_session() as s:
            from core.models import Article
            art = s.query(Article).one()
            assert art.status == "rejected"
            assert art.posted_at is None, (
                "rejections must not set posted_at or they inflate posting stats"
            )
        assert db.get_unposted_articles("VIC") == []

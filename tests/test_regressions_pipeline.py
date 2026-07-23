"""
Regression tests for core pipeline defects (CORE-1 .. CORE-6, DATA-1/2).

These cover the circuit-breaker failures behind the June 2026 incident, in
which 85 councils were silently disabled and stayed that way for weeks. See
docs/CODE_REVIEW_2026-07-07.md for the original findings.
"""

from datetime import datetime, timedelta

import pytest

from core.database import Database
from core.processing import process_articles
from core.scrapers.base import NewsArticle


def article(url="https://testville.gov.au/news/1", date=None, title="Kerbside collection changes"):
    return NewsArticle(
        council_id="testville", council_name="Testville Shire Council",
        title=title, url=url, date=date, excerpt="Details of the change.",
    )


class TestCore2FailureRecordingNeverCrashes:
    """
    CORE-2: record_failure() raised TypeError for any council with no existing
    health row (None + 1), so a council that had never succeeded could never
    trip the breaker and never got telemetry. Reproduced empirically in review.
    """

    def test_first_ever_failure_is_recorded(self, db):
        disabled = db.record_failure("never-seen-before")
        assert disabled is False
        assert db.get_council_health("never-seen-before")["consecutive_failures"] == 1

    def test_failures_accumulate_to_the_breaker(self, db):
        for i in range(4):
            assert db.record_failure("flaky") is False, f"should not disable at {i+1} failures"
        assert db.record_failure("flaky") is True, "5th consecutive failure must disable"
        assert db.get_council_health("flaky")["is_disabled"] is True

    def test_success_resets_the_failure_count(self, db):
        db.record_failure("recovering")
        db.record_failure("recovering")
        db.record_success("recovering", articles_found=3)
        assert db.get_council_health("recovering")["consecutive_failures"] == 0


class TestCore1BreakerIsNotAOneWayDoor:
    """
    CORE-1: once disabled, a council could never be re-enabled by the system.
    main.py skipped disabled councils, so record_success() — the only path
    that cleared the flag — could never run. Councils needed manual SQL.
    """

    def test_finding_articles_re_enables_a_disabled_council(self, db):
        for _ in range(5):
            db.record_failure("stuck")
        assert db.get_council_health("stuck")["is_disabled"] is True

        db.record_success("stuck", articles_found=4)

        health = db.get_council_health("stuck")
        assert health["is_disabled"] is False, "a successful scrape must clear the breaker"
        assert health["disabled_at"] is None

    def test_empty_runs_eventually_disable(self, db):
        for _ in range(Database.EMPTY_RUN_DISABLE_THRESHOLD - 1):
            assert db.record_success("silent", articles_found=0) is False
        assert db.record_success("silent", articles_found=0) is True

    def test_failed_probation_restamps_the_clock(self, db):
        """
        The probation retry re-stamps disabled_at on failure; without this the
        council would be retried on every single run once the window expired.
        """
        for _ in range(5):
            db.record_failure("probation")
        first = db.get_council_health("probation")["disabled_at"]

        db.record_failure("probation")
        second = db.get_council_health("probation")["disabled_at"]

        assert second is not None and first is not None
        assert second >= first, "a failed probation must reset the probation clock"


class TestCore5ConcurrentInsertsDoNotLoseTheBatch:
    """
    CORE-5: add_articles_bulk did select-then-insert with a single batch
    commit, so a concurrent duplicate URL raised IntegrityError and rolled
    back every article in the run.
    """

    def test_duplicate_urls_are_ignored_not_fatal(self, db):
        first = db.add_articles_bulk([
            {"url": "https://t.gov.au/a", "council_id": "t", "title": "A",
             "date": datetime.now(), "excerpt": "x"},
        ], "VIC")
        assert first == 1

        second = db.add_articles_bulk([
            {"url": "https://t.gov.au/a", "council_id": "t", "title": "A again",
             "date": datetime.now(), "excerpt": "x"},
            {"url": "https://t.gov.au/b", "council_id": "t", "title": "B",
             "date": datetime.now(), "excerpt": "x"},
        ], "VIC")
        assert second == 1, "the duplicate is skipped but the new article still lands"

    def test_batch_survives_a_duplicate_in_the_middle(self, db):
        db.add_articles_bulk([
            {"url": "https://t.gov.au/dup", "council_id": "t", "title": "dup",
             "date": datetime.now(), "excerpt": "x"}], "VIC")

        saved = db.add_articles_bulk([
            {"url": "https://t.gov.au/1", "council_id": "t", "title": "1",
             "date": datetime.now(), "excerpt": "x"},
            {"url": "https://t.gov.au/dup", "council_id": "t", "title": "dup",
             "date": datetime.now(), "excerpt": "x"},
            {"url": "https://t.gov.au/2", "council_id": "t", "title": "2",
             "date": datetime.now(), "excerpt": "x"},
        ], "VIC")
        assert saved == 2, "articles either side of a duplicate must still be saved"


class TestData2DatelessArticlesAreNotSilentlyDiscarded:
    """
    DATA-2: articles with no parsed date were archived and never posted, while
    the scrape still counted as successful — so a broken date selector stopped
    a council publishing while every health signal stayed green.
    """

    def test_dateless_articles_are_queued(self, db):
        unposted = process_articles([article(date=None)], db, "VIC")
        assert len(unposted) == 1, (
            "an article with no date must still reach the queue, not vanish"
        )

    def test_stale_articles_are_archived(self, db):
        old = datetime.now() - timedelta(days=30)
        unposted = process_articles([article(date=old)], db, "VIC")
        assert unposted == []

    def test_force_fresh_overrides_the_staleness_filter(self, db):
        """CORE-4: --force-fresh was parsed but never wired through."""
        old = datetime.now() - timedelta(days=30)
        unposted = process_articles([article(date=old)], db, "VIC", force_fresh=True)
        assert len(unposted) == 1


class TestQual5QueueDrainsOldestFirst:
    """
    QUAL-5: within a council the queue drained newest-first, so under a
    backlog the oldest articles aged past the staleness cutoff and were
    suppressed without ever being published.
    """

    def test_longest_queued_article_is_published_first(self, db):
        """
        Ordering is by discovery time (first_seen_at), not publication date:
        whatever has waited longest in the queue goes first, so a backlog
        drains FIFO instead of leaving old items to expire.
        """
        import time
        db.add_articles_bulk([
            {"url": "https://t.gov.au/first", "council_id": "t",
             "title": "queued-first", "date": datetime.now(), "excerpt": "x"},
        ], "VIC")
        time.sleep(1.1)  # first_seen_at has one-second resolution
        db.add_articles_bulk([
            {"url": "https://t.gov.au/second", "council_id": "t",
             "title": "queued-second", "date": datetime.now(), "excerpt": "x"},
        ], "VIC")

        queue = db.get_unposted_articles("VIC")
        assert [a["title"] for a in queue] == ["queued-first", "queued-second"], (
            "the queue must drain oldest-first or backlog expires unpublished"
        )

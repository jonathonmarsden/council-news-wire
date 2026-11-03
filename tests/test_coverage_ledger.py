"""Tests for the coverage ledger: health defined by output, not by scrape success."""
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "coverage_ledger", Path(__file__).resolve().parents[1] / "scripts/monitoring/coverage_ledger.py")
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)

NOW = datetime(2026, 11, 3, 12, 0)
HEALTHY = {"is_disabled": False, "consecutive_failures": 0, "consecutive_empty_runs": 0,
           "last_success_at": NOW - timedelta(hours=6)}


# ---- the pure decision ------------------------------------------------------

def test_posting_wins_over_everything_else_when_healthy():
    assert ledger.classify(HEALTHY, {"posted_window": 3, "seen_window": 5}, NOW)[0] == "posting"


def test_disabled_after_errors_is_broken_error():
    h = {**HEALTHY, "is_disabled": True, "consecutive_failures": 10}
    assert ledger.classify(h, {"posted_window": 2}, NOW)[0] == "broken_error"


def test_disabled_after_empty_runs_is_broken_empty():
    h = {**HEALTHY, "is_disabled": True, "consecutive_empty_runs": 37}
    assert ledger.classify(h, {}, NOW)[0] == "broken_empty"


def test_city_of_sydney_shape_is_stale_only():
    # Healthy scrape, finds items every week, none ever posted: wrong page.
    facts = {"seen_window": 4, "posted_window": 0, "archived_window": 4, "last_posted": None}
    bucket, detail = ledger.classify(HEALTHY, facts, NOW)
    assert bucket == "stale_only"
    assert "4 found" in detail and "4 archived" in detail


def test_small_shire_with_nothing_new_is_quiet():
    facts = {"seen_window": 0, "posted_window": 0, "last_posted": NOW - timedelta(days=40), "median_gap_days": 45.0}
    assert ledger.classify(HEALTHY, facts, NOW)[0] == "quiet"


def test_regular_poster_gone_silent_is_overdue():
    facts = {"seen_window": 0, "posted_window": 0, "last_posted": NOW - timedelta(days=40), "median_gap_days": 3.0}
    bucket, detail = ledger.classify(HEALTHY, facts, NOW)
    assert bucket == "overdue"
    assert "silent 40d" in detail


def test_overdue_needs_more_than_the_window_even_for_daily_posters():
    facts = {"seen_window": 0, "posted_window": 0, "last_posted": NOW - timedelta(days=20), "median_gap_days": 1.0}
    assert ledger.classify(HEALTHY, facts, NOW)[0] == "quiet"


def test_no_health_row_is_never_scraped():
    assert ledger.classify(None, {}, NOW)[0] == "never_scraped"


@pytest.mark.parametrize("days,expected", [
    ([1, 2, 3, 4, 5], 1.0),
    ([1, 8, 15, 29], 7.0),
    ([1, 1, 1, 2, 3], 1.0),   # same-day posts count once
    ([1, 2], None),           # too few to judge
])
def test_median_gap(days, expected):
    stamps = [datetime(2026, 1, d, 9) for d in days]
    assert ledger.median_gap_days(stamps) == expected


# ---- against the real schema ------------------------------------------------

def _seed(db, council, url, posted_days_ago=None, seen_days_ago=1, status=None):
    db.add_articles_bulk([{"url": url, "council_id": council, "title": url[-12:],
                           "date": NOW - timedelta(days=seen_days_ago), "excerpt": "x"}], "NSW")
    from core.models import Article
    with db.get_session() as s:
        a = s.query(Article).filter(Article.url == url).one()
        a.first_seen_at = NOW - timedelta(days=seen_days_ago)
        if posted_days_ago is not None:
            a.status = "posted"
            a.posted_at = NOW - timedelta(days=posted_days_ago)
        elif status:
            a.status = status
        s.commit()


def test_ledger_from_the_database(db, tmp_path):
    # posting council with a 7-day rhythm; a stale-only council; a quiet one; a broken one
    for i, d in enumerate((1, 8, 15, 22)):
        _seed(db, "rhythm", f"https://rhythm.nsw.gov.au/news/{i}", posted_days_ago=d, seen_days_ago=d)
    for i in range(3):
        _seed(db, "sydney", f"https://sydney.nsw.gov.au/news/{i}", seen_days_ago=5 + i, status="archived")
    _seed(db, "quiet", "https://quiet.nsw.gov.au/news/1", posted_days_ago=90, seen_days_ago=90)
    for cid in ("rhythm", "sydney", "quiet"):
        db.record_success(cid, articles_found=1)
    for _ in range(5):
        db.record_failure("dubbo")

    states = tmp_path / "states" / "nsw"
    states.mkdir(parents=True)
    (states / "councils.json").write_text('{"councils": [' + ",".join(
        f'{{"id": "{c}", "name": "{c.title()} Council", "enabled": true}}'
        for c in ("rhythm", "sydney", "quiet", "dubbo", "fresh")) + "]}")

    councils = ledger.load_councils(tmp_path / "states")
    result = ledger.build_ledger(councils, ledger.load_health(db), ledger.build_facts(db, NOW), NOW)

    by_id = {r["id"]: r["bucket"] for r in result["rows"]}
    assert by_id == {"rhythm": "posting", "sydney": "stale_only", "quiet": "quiet",
                     "dubbo": "broken_error", "fresh": "never_scraped"}
    assert result["counts"]["posting"] == 1
    # 1 posting of the 4 that are not merely quiet
    assert result["active_coverage"] == 25.0
    text = ledger.render(result)
    assert "STALE ONLY (1)" in text and "Sydney Council" in text
    assert "BROKEN ERROR (1)" in text

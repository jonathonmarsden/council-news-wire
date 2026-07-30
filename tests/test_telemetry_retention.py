"""Tests for telemetry retention pruning (scripts/maintenance/cleanup_remote_db.py).

Telemetry tables are append-only diagnostics that grew to ~440k rows / 78 MB in
production - three times the size of the article archive. These tests prove the
pruner deletes only aged telemetry, never articles, and tolerates schemas that
lack the expected tables/columns.
"""
import sys
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

sys.path.append("scripts/maintenance")
from scripts.maintenance.cleanup_remote_db import prune_telemetry, RETENTION_DAYS


@pytest.fixture
def telemetry_db(db):
    """Seed scraper_stats with old and recent rows.

    The real table (created by the app's models) timestamps rows in `run_at`,
    which is one of the columns prune_telemetry looks for.
    """
    with db.get_session() as s:
        old = datetime.now() - timedelta(days=200)
        recent = datetime.now() - timedelta(days=5)
        from core.models import ScraperStats
        for i, ts in enumerate([old, old, old, recent, recent], start=1):
            s.add(ScraperStats(id=i, council_id="x", run_at=ts,
                               articles_found=0, articles_saved=0))
        s.commit()
    return db


def _count(db, table):
    with db.get_session() as s:
        return s.execute(text(f"SELECT count(*) FROM {table}")).scalar()


def test_prunes_only_rows_older_than_window(telemetry_db):
    assert _count(telemetry_db, "scraper_stats") == 5
    deleted = prune_telemetry(telemetry_db, {"scraper_stats": 90})
    assert deleted["scraper_stats"] == 3          # the three 200-day-old rows
    assert _count(telemetry_db, "scraper_stats") == 2  # recent rows survive


def test_does_not_touch_articles(telemetry_db):
    """The article archive is content, not telemetry - it must never be pruned."""
    telemetry_db.add_articles_bulk([{
        "url": "https://x.gov.au/a", "council_id": "c", "title": "T",
        "date": datetime.now() - timedelta(days=500), "excerpt": "e",
    }], "VIC")
    before = _count(telemetry_db, "articles")
    prune_telemetry(telemetry_db, {"scraper_stats": 90})
    assert _count(telemetry_db, "articles") == before


def test_missing_table_is_skipped(db):
    # No telemetry tables at all - must not raise.
    assert prune_telemetry(db, {"nonexistent_table": 30}) == {}


def test_table_without_timestamp_column_is_skipped(db):
    with db.get_session() as s:
        s.execute(text("CREATE TABLE no_ts_table (id INTEGER PRIMARY KEY, msg TEXT)"))
        s.execute(text("INSERT INTO no_ts_table (id, msg) VALUES (1, 'x')"))
        s.commit()
    result = prune_telemetry(db, {"no_ts_table": 30})
    assert "no_ts_table" not in result          # skipped, not deleted
    assert _count(db, "no_ts_table") == 1       # row survives


def test_default_windows_are_sane():
    # Guard against someone setting a window so short it destroys useful history.
    assert RETENTION_DAYS["scraper_stats"] >= 30
    assert RETENTION_DAYS["run_summaries"] >= 30
    assert RETENTION_DAYS["log_events"] >= 14

import sys
import os
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from core.constants import GARBAGE_TITLES
from core.database import Database

FAR_FUTURE_DAYS = 366


def far_future_cutoff(now=None):
    """Dates later than this are treated as mis-parsed."""
    from datetime import datetime, timedelta
    return (now or datetime.now()) + timedelta(days=FAR_FUTURE_DAYS)


def archive_far_future(session, now=None) -> int:
    """Archive unposted articles dated implausibly far in the future.

    A mis-parsed date (wrong year, garbage text) can land years ahead; such a
    row would sit in the queue for ever. It is archived, not deleted, or the
    scraper would rediscover and repost it.

    The cutoff moves with the calendar. It was once the literal '2027-01-01',
    which from January 2027 would have archived every current story and
    stamped each as posted today. Posted rows and posted_at are never touched.
    """
    result = session.execute(
        text("UPDATE articles SET status = 'archived' "
             "WHERE date > :cutoff AND status NOT IN ('archived', 'posted')"),
        {"cutoff": far_future_cutoff(now)},
    )
    return result.rowcount or 0


def cleanup_malformed_posts(db=None):
    db = db or Database()
    print("Connecting to Database (PostgreSQL)...")
    
    with db.get_session() as session:
        # 1. Archive unposted articles dated implausibly far in the future.
        archived = archive_far_future(session)
        if archived:
            print(f"Archived {archived} far-future rows.")

        # 2. Deletes titles that are just "Posted ..."
        print("Scanning for 'Posted ...' titles...")
        # Get candidates first to check for digits
        rows = session.execute(text("SELECT id, council_id, title FROM articles WHERE title ILIKE 'Posted %'")).fetchall()
        
        count = 0
        for row in rows:
            if any(char.isdigit() for char in row.title):
                print(f"  - Deleting: {row.title}")
                session.execute(text("DELETE FROM articles WHERE id = :id"), {"id": row.id})
                count += 1
        print(f"Deleted {count} 'Posted ...' rows.")

        # 3. Delete copyright titles
        print("Scanning for copyright titles...")
        session.execute(text("DELETE FROM articles WHERE title ILIKE '©%' OR title ILIKE '&copy;%'"))

        # 4. Delete Garbage Phrases (from centralized constants)
        print("Scanning for garbage phrases...")
        for g in GARBAGE_TITLES:
             # Case insensitive match
            stmt = text("DELETE FROM articles WHERE lower(title) = lower(:title)")
            result = session.execute(stmt, {"title": g})
            if result.rowcount > 0:
                print(f"Deleted {result.rowcount} garbage rows: '{g}'")

        session.commit()

    prune_telemetry(db)

    print("Cleanup complete on PostgreSQL.")


# Retention windows for operational telemetry. These tables are append-only
# diagnostics: useful for recent troubleshooting and health trends, worthless
# after a few months, and they grow without bound. Before this pruning existed
# they held ~440k rows / 78 MB — three times the size of the article archive
# they describe. Article rows are NEVER pruned here: they are the project's
# actual content, and deleting them would let the scrapers rediscover and
# repost old stories.
RETENTION_DAYS = {
    "scraper_stats": 90,   # per-council run rows; 90 days covers seasonal trends
    "run_summaries": 90,
    "log_events": 30,      # verbose; 30 days is plenty for incident review
}


def prune_telemetry(db, retention=None):
    """Delete telemetry rows older than their retention window.

    Returns {table: rows_deleted}. Skips any table that does not exist or has
    no timestamp column, so this is safe to run against older schemas.
    """
    retention = retention or RETENTION_DAYS
    deleted = {}
    # Introspect via SQLAlchemy so this works on both PostgreSQL (production)
    # and SQLite (tests) rather than depending on information_schema.
    from sqlalchemy import inspect as sa_inspect
    from datetime import datetime, timedelta

    with db.get_session() as session:
        inspector = sa_inspect(session.get_bind())
        present = set(inspector.get_table_names())
        preferred = ("created_at", "timestamp", "run_at", "started_at", "recorded_at")
        for table, days in retention.items():
            if table not in present:
                continue
            cols = {c["name"]: c for c in inspector.get_columns(table)}
            tscol = next((c for c in preferred if c in cols), None)
            if not tscol:
                print(f"  {table}: no timestamp column, skipped")
                continue
            cutoff = datetime.now() - timedelta(days=int(days))
            res = session.execute(
                text(f"DELETE FROM {table} WHERE {tscol} < :cutoff"), {"cutoff": cutoff}
            )
            deleted[table] = res.rowcount or 0
            print(f"  {table}: pruned {deleted[table]} rows older than {days}d")
        session.commit()
    return deleted


if __name__ == "__main__":
    cleanup_malformed_posts()
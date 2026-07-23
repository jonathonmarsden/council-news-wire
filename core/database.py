"""
Database module for Council News Bot.

Handles database operations via SQLAlchemy using PostgreSQL.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from dateutil import parser
from typing import List, Optional, Dict, Union
from sqlalchemy import create_engine, select, update, func, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import insert as pg_upsert

from core.models import Base, Article, CouncilHealth, ScraperStats, LogEvent, RunSummary

class Database:
    """SQLAlchemy database handler."""
    
    def __init__(self, db_url: str = None, create_tables: bool = False):
        """
        Initialize database connection.
        Requires DATABASE_URL env var (Postgres) unless db_url is provided.
        """
        self.db_url = db_url or os.environ.get("DATABASE_URL")
        if not self.db_url:
            raise RuntimeError("DATABASE_URL is required. SQLite support has been removed.")

        # Create Engine
        self.engine = create_engine(self.db_url)

        # Schema is managed by Alembic (run on container start). create_all
        # here used to race it: a fresh DB got tables with no alembic_version
        # stamp ("relation already exists" on upgrade) and missing migrations
        # were masked everywhere except prod. Opt in explicitly for tests.
        if create_tables:
            Base.metadata.create_all(self.engine)

        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def get_session(self) -> Session:
        """Get a SQLAlchemy session."""
        return self.SessionLocal()
    
    def _upsert_stmt(self, table, values, index_elements):
        """Helper to generate Postgres upsert statement."""
        stmt = pg_upsert(table).values(values)
        return stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_=values
        )

    def add_log_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        run_id: Optional[str] = None,
        state: Optional[str] = None,
        council_id: Optional[str] = None,
        event_metadata: Optional[Dict] = None,
    ) -> None:
        """Persist a structured log event."""
        with self.get_session() as session:
            event = LogEvent(
                run_id=run_id,
                state=state,
                council_id=council_id,
                event_type=event_type,
                severity=severity,
                message=message,
                event_metadata=event_metadata,
            )
            session.add(event)
            session.commit()

    def upsert_run_summary(self, summary: Dict) -> None:
        """Create or update a run summary by run_id."""
        if not summary.get("run_id"):
            raise ValueError("run_id is required for run summaries")

        values = {
            "run_id": summary["run_id"],
            "state": summary["state"],
            "started_at": summary["started_at"],
            "ended_at": summary["ended_at"],
            "duration_ms": summary["duration_ms"],
            "councils_scraped": summary.get("councils_scraped", 0),
            "articles_found": summary.get("articles_found", 0),
            "articles_posted": summary.get("articles_posted", 0),
            "errors_count": summary.get("errors_count", 0),
            "warnings_count": summary.get("warnings_count", 0),
        }

        with self.get_session() as session:
            stmt = self._upsert_stmt(RunSummary.__table__, values, ["run_id"])
            session.execute(stmt)
            session.commit()

    def article_exists(self, url: str) -> bool:
        """Check if an article URL has already been seen."""
        with self.get_session() as session:
            stmt = select(Article.id).where(Article.url == url)
            return session.execute(stmt).first() is not None
            
    def is_posted(self, url: str) -> bool:
        """Check if an article has been posted."""
        with self.get_session() as session:
            stmt = select(Article.id).where(
                and_(Article.url == url, Article.posted_at.is_not(None))
            )
            return session.execute(stmt).first() is not None

    def add_article(self, article: Dict, state: str) -> int:
        """Add a new article to the database."""
        with self.get_session() as session:
            # Check exist first to avoid auto-increment burning on Postgres
            existing = session.execute(select(Article).where(Article.url == article['url'])).scalar_one_or_none()
            if existing:
                return existing.id

            new_article = Article(
                url=article['url'],
                council_id=article['council_id'],
                title=article['title'],
                date=article.get('date'),
                excerpt=article.get('excerpt'),
                state=state,
                status='new'
            )
            session.add(new_article)
            try:
                session.commit()
                session.refresh(new_article)
                return new_article.id
            except Exception:
                session.rollback()
                # Race condition fallback
                existing = session.execute(select(Article).where(Article.url == article['url'])).scalar_one_or_none()
                return existing.id if existing else -1

    @staticmethod
    def _coerce_date(value):
        """
        Accept either a datetime or an ISO-8601 string for the date column.

        NewsArticle.to_dict() serialises dates to ISO strings. PostgreSQL
        silently casts those on insert, but that implicit coercion is a
        portability trap (SQLite rejects it outright) and hides type errors.
        Normalise at the boundary instead of relying on the driver.
        """
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return parser.parse(value)
            except (ValueError, TypeError):
                return None
        return None

    def add_articles_bulk(self, articles: List[Dict], state: str, status: str = 'new') -> int:
        """Add multiple articles using bulk insert ignore logic."""
        if not articles:
            return 0

        # Deduplicate incoming list by URL
        unique_articles = {a['url']: a for a in articles}.values()
        
        count = 0
        with self.get_session() as session:
            for a in unique_articles:
                stmt = select(Article.id).where(Article.url == a['url'])
                if session.execute(stmt).first():
                    continue
                session.add(Article(
                    url=a['url'],
                    council_id=a['council_id'],
                    title=a['title'],
                    date=self._coerce_date(a.get('date')),
                    excerpt=a.get('excerpt'),
                    state=state,
                    status=status
                ))
                # Per-row commit: a concurrent run inserting the same URL
                # between our SELECT and a single batch commit used to raise
                # IntegrityError at the end and roll back the ENTIRE batch.
                try:
                    session.commit()
                    count += 1
                except IntegrityError:
                    session.rollback()
        return count

    # Dead-letter an article after this many failed (transient) post attempts
    MAX_POST_ATTEMPTS = 5

    def mark_as_posted(self, url: str, handle: str):
        """Mark an article as posted."""
        with self.get_session() as session:
            stmt = update(Article).where(Article.url == url).values(
                posted_at=func.now(),
                posted_to_handle=handle,
                status='posted'
            )
            session.execute(stmt)
            session.commit()

    def mark_as_rejected(self, url: str, reason: str):
        """
        Permanently reject an article (validation failure / API 4xx).
        Leaves posted_at NULL so posting stats don't count rejections;
        get_unposted_articles excludes it via status.
        """
        with self.get_session() as session:
            stmt = update(Article).where(Article.url == url).values(
                posted_at=None,
                posted_to_handle=reason,
                status='rejected'
            )
            session.execute(stmt)
            session.commit()

    def claim_article(self, url: str) -> bool:
        """
        Atomically claim an article for posting. Returns True if this process
        won the claim; False means another process already claimed/posted it.
        Claiming sets posted_at so concurrent queue reads skip the row; the
        claim is confirmed by mark_as_posted or rolled back by release_claim.
        """
        with self.get_session() as session:
            stmt = update(Article).where(
                and_(Article.url == url, Article.posted_at.is_(None))
            ).values(posted_at=func.now(), posted_to_handle='CLAIMED')
            result = session.execute(stmt)
            session.commit()
            return result.rowcount > 0

    def release_claim(self, url: str) -> bool:
        """
        Roll back a claim after a transient post failure so the article is
        retried next run. Increments attempt_count; after MAX_POST_ATTEMPTS
        the article is dead-lettered (status='failed') instead of retried.
        Returns True if the article was dead-lettered.
        """
        with self.get_session() as session:
            obj = session.execute(select(Article).where(Article.url == url)).scalar_one_or_none()
            if not obj:
                return False
            obj.attempt_count = (obj.attempt_count or 0) + 1
            obj.posted_at = None
            obj.posted_to_handle = None
            dead = obj.attempt_count >= self.MAX_POST_ATTEMPTS
            if dead:
                obj.status = 'failed'
            session.commit()
            return dead

    def get_unposted_articles(self, state: str, limit: int = 50, suppress_stale: bool = True) -> List[Dict]:
        """
        Get unposted articles for a specific state (Round Robin).

        suppress_stale=False (--force-fresh) skips the 7-day auto-suppression,
        which would otherwise immediately re-suppress the old articles the
        caller is trying to force out.
        """
        fetch_limit = max(limit * 5, 200)
        
        with self.get_session() as session:
            stmt = select(Article).where(
                and_(
                    func.upper(Article.state) == state.upper(),
                    Article.posted_at.is_(None),
                    Article.status.not_in(['archived', 'rejected', 'failed'])
                )
            ).order_by(Article.first_seen_at.desc()).limit(fetch_limit)
            
            objs = session.execute(stmt).scalars().all()
            
            # Convert to dicts
            raw_articles = []
            
            # Filter for freshness (User Request: < 7 days old)
            cutoff_date = datetime.now() - timedelta(days=7)
            
            for o in objs:
                is_too_old = False
                if suppress_stale and o.date:
                    try:
                        # o.date is a datetime object (post DateTime migration)
                        dt = o.date
                        # Strip timezone for naive comparison if needed
                        if dt.tzinfo is not None:
                            dt = dt.replace(tzinfo=None)
                        if dt < cutoff_date:
                            is_too_old = True
                    except Exception:
                        # Keep it if we can't compare (safer than suppressing valid items)
                        pass
                
                if is_too_old:
                    # Auto-suppress to clean the queue (func.now() = DB time,
                    # consistent with mark_as_posted; datetime.now() here was
                    # container-local Sydney time mixed into UTC data)
                    o.status = 'suppressed_too_old'
                    o.posted_at = func.now()
                else:
                    raw_articles.append({
                        'id': o.id, 'url': o.url, 'council_id': o.council_id,
                        'title': o.title, 'date': o.date, 'excerpt': o.excerpt,
                        'state': o.state, 'first_seen_at': o.first_seen_at
                    })
            
            # Commit the suppressions
            session.commit()

        if not raw_articles:
            return []
            
        # Group by council
        council_queues = {}
        council_order = [] 
        
        for article in raw_articles:
            c_id = article['council_id']
            if c_id not in council_queues:
                council_queues[c_id] = []
                council_order.append(c_id)
            council_queues[c_id].append(article)
            
        # Oldest-first within each council: the fetch above is newest-first
        # (to grab the most recent 200 overall), but draining LIFO per
        # council let backlog age past 7 days and expire unposted.
        for queue in council_queues.values():
            queue.sort(key=lambda a: a['first_seen_at'] or datetime.min)

        # Round robin
        varied_articles = []
        while len(varied_articles) < limit and any(council_queues.values()):
            for c_id in council_order:
                if council_queues[c_id]:
                    varied_articles.append(council_queues[c_id].pop(0))
                    if len(varied_articles) >= limit:
                        break
                        
        return varied_articles

    def get_council_health(self, council_id: str) -> Dict:
        """Get health status."""
        with self.get_session() as session:
            obj = session.get(CouncilHealth, council_id)
            if obj:
                return {
                    'council_id': obj.council_id,
                    'consecutive_failures': obj.consecutive_failures,
                    'is_disabled': obj.is_disabled,
                    'disabled_at': obj.disabled_at,
                    'consecutive_empty_runs': obj.consecutive_empty_runs
                }
            return {
                'council_id': council_id,
                'consecutive_failures': 0,
                'is_disabled': False,
                'disabled_at': None,
                'consecutive_empty_runs': 0
            }

    # Disable a council after this many consecutive empty scrape runs.
    # Empty runs are silent failures (scraper returns 0 articles with no error).
    EMPTY_RUN_DISABLE_THRESHOLD = 20

    def record_success(self, council_id: str, articles_found: int = 0) -> bool:
        """
        Record a scrape run result. Returns True if the council was disabled
        due to too many consecutive empty runs (articles_found == 0).
        """
        with self.get_session() as session:
            obj = session.get(CouncilHealth, council_id)
            current_empty = obj.consecutive_empty_runs if obj else 0
            new_empty = 0 if articles_found > 0 else current_empty + 1

            if not obj:
                obj = CouncilHealth(council_id=council_id)
                session.add(obj)

            obj.consecutive_failures = 0
            obj.last_success_at = func.now()
            obj.consecutive_empty_runs = new_empty

            # Empty-run circuit breaker with probation: main.py re-tries
            # disabled councils once disabled_at is old enough, so a failed
            # probation must re-stamp the clock or it would retry every run.
            if articles_found > 0:
                # Re-enable on successful article fetch (also passes probation)
                obj.is_disabled = False
                obj.disabled_at = None
            elif obj.is_disabled:
                # Failed probation (still empty): reset the probation clock
                obj.disabled_at = func.now()
            elif new_empty >= self.EMPTY_RUN_DISABLE_THRESHOLD:
                obj.is_disabled = True
                obj.disabled_at = func.now()

            session.commit()
            return obj.is_disabled

    def record_failure(self, council_id: str) -> bool:
        """Record failure."""
        with self.get_session() as session:
            obj = session.get(CouncilHealth, council_id)
            if not obj:
                # Column defaults apply at INSERT, so counters are None pre-flush
                obj = CouncilHealth(council_id=council_id, consecutive_failures=0,
                                    consecutive_empty_runs=0, is_disabled=False)
                session.add(obj)

            obj.consecutive_failures = (obj.consecutive_failures or 0) + 1
            obj.last_failure_at = func.now()

            # >= 5 failures disables; a failure while already disabled is a
            # failed probation attempt and re-stamps the probation clock.
            if obj.consecutive_failures >= 5 or obj.is_disabled:
                obj.is_disabled = True
                obj.disabled_at = func.now()
                
            session.commit()
            return obj.is_disabled

    def log_scraper_run(self, council_id: str, articles_found: int, status: str, duration_ms: int, articles_saved: int = 0):
        """Log stats."""
        with self.get_session() as session:
            stat = ScraperStats(
                council_id=council_id,
                articles_found=articles_found,
                articles_saved=articles_saved,
                status=status,
                duration_ms=duration_ms
            )
            session.add(stat)
            session.commit()
            
    def get_stats(self, state: str) -> Dict:
        """Get basic stats."""
        with self.get_session() as session:
            total = session.query(func.count(Article.id)).where(func.upper(Article.state) == state.upper()).scalar()
            posted = session.query(func.count(Article.id)).where(
                and_(func.upper(Article.state) == state.upper(), Article.posted_at.is_not(None))
            ).scalar()
            
            return {
                "total_articles": total,
                "posted_articles": posted,
                "backlog": total - posted
            }


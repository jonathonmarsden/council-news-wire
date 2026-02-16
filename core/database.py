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
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import insert as pg_upsert

from core.models import Base, Article, CouncilHealth, ScraperStats, LogEvent, RunSummary

class Database:
    """SQLAlchemy database handler."""
    
    def __init__(self, db_url: str = None):
        """
        Initialize database connection.
        Requires DATABASE_URL env var (Postgres) unless db_url is provided.
        """
        self.db_url = db_url or os.environ.get("DATABASE_URL")
        if not self.db_url:
            raise RuntimeError("DATABASE_URL is required. SQLite support has been removed.")

        # Create Engine
        self.engine = create_engine(self.db_url)
        
        # Create Tables (if not exist)
        # Note: In production with Alembic, we might skip this or use alembic upgrade head
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

    def add_articles_bulk(self, articles: List[Dict], state: str, status: str = 'new') -> int:
        """Add multiple articles using bulk insert ignore logic."""
        if not articles:
            return 0
        
        # Deduplicate incoming list by URL
        unique_articles = {a['url']: a for a in articles}.values()
        
        count = 0
        with self.get_session() as session:
            for a in unique_articles:
                # We do row-by-row check for simplicity in ORM to handle ignore logic
                # For massive scale, Core Insert with on_conflict_do_nothing is better
                # but this is fine for batches of ~20-50
                stmt = select(Article.id).where(Article.url == a['url'])
                if not session.execute(stmt).first():
                    new_a = Article(
                        url=a['url'],
                        council_id=a['council_id'],
                        title=a['title'],
                        date=a.get('date'),
                        excerpt=a.get('excerpt'),
                        state=state,
                        status=status
                    )
                    session.add(new_a)
                    count += 1
            session.commit()
        return count

    def mark_as_posted(self, url: str, handle: str):
        """Mark an article as posted."""
        with self.get_session() as session:
            stmt = update(Article).where(Article.url == url).values(
                posted_at=func.now(),
                posted_to_handle=handle
            )
            session.execute(stmt)
            session.commit()

    def get_unposted_articles(self, state: str, limit: int = 50) -> List[Dict]:
        """Get unposted articles for a specific state (Round Robin)."""
        fetch_limit = max(limit * 5, 200)
        
        with self.get_session() as session:
            stmt = select(Article).where(
                and_(
                    func.upper(Article.state) == state.upper(),
                    Article.posted_at.is_(None),
                    Article.status != 'archived'
                )
            ).order_by(Article.first_seen_at.desc()).limit(fetch_limit)
            
            objs = session.execute(stmt).scalars().all()
            
            # Convert to dicts
            raw_articles = []
            
            # Filter for freshness (User Request: < 7 days old)
            cutoff_date = datetime.now() - timedelta(days=7)
            
            for o in objs:
                is_too_old = False
                if o.date:
                    try:
                        # Parse date string. Assume dayfirst for Australia unless obvious
                        dt = parser.parse(o.date, fuzzy=True, dayfirst=True)
                        if dt < cutoff_date:
                            is_too_old = True
                    except Exception:
                        # Keep it if we can't parse it (safer than suppressing valid items)
                        pass
                
                if is_too_old:
                    # Auto-suppress to clean the queue
                    o.status = 'suppressed_too_old'
                    o.posted_at = datetime.now()
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
                    'consecutive_empty_runs': obj.consecutive_empty_runs
                }
            return {
                'council_id': council_id,
                'consecutive_failures': 0,
                'is_disabled': False,
                'consecutive_empty_runs': 0
            }

    def record_success(self, council_id: str, articles_found: int = 0):
        """Record success."""
        with self.get_session() as session:
            # Get current empty runs
            obj = session.get(CouncilHealth, council_id)
            current_empty = obj.consecutive_empty_runs if obj else 0
            new_empty = 0 if articles_found > 0 else current_empty + 1
            
            # SQLAlchemy Merge is closest to Upsert, but explicit object manipulation is cleaner here
            if not obj:
                obj = CouncilHealth(council_id=council_id)
                session.add(obj)
            
            obj.consecutive_failures = 0
            obj.last_success_at = func.now()
            obj.is_disabled = False
            obj.disabled_at = None
            obj.consecutive_empty_runs = new_empty
            session.commit()

    def record_failure(self, council_id: str) -> bool:
        """Record failure."""
        with self.get_session() as session:
            obj = session.get(CouncilHealth, council_id)
            if not obj:
                obj = CouncilHealth(council_id=council_id)
                session.add(obj)
            
            obj.consecutive_failures += 1
            obj.last_failure_at = func.now()
            
            if obj.consecutive_failures >= 5:
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


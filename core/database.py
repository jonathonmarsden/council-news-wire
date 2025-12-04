"""
Database module for Council News Bot.

Handles SQLite database operations for tracking scraped articles and posting history.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Set, Tuple
from core.config import DB_PATH

class Database:
    """SQLite database handler."""
    
    def __init__(self, db_path: str = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses default from config.
        """
        self.db_path = db_path if db_path else str(DB_PATH)
        
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        # Increase timeout to 60 seconds to handle concurrent access during heavy scrapes
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize the database schema."""
        with self._get_conn() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
            
            # Articles table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    council_id TEXT NOT NULL,
                    title TEXT,
                    date TEXT,
                    excerpt TEXT,
                    state TEXT NOT NULL,
                    status TEXT DEFAULT 'new',
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    posted_at TIMESTAMP,
                    posted_to_handle TEXT
                )
            """)
            
            # Migration: Add status column if it doesn't exist
            try:
                conn.execute("ALTER TABLE articles ADD COLUMN status TEXT DEFAULT 'new'")
            except sqlite3.OperationalError:
                # Column likely already exists
                pass
            
            # Create index for faster lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON articles(url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_state_posted ON articles(state, posted_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON articles(status)")
            
            # Council Health table (Circuit Breaker)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS council_health (
                    council_id TEXT PRIMARY KEY,
                    consecutive_failures INTEGER DEFAULT 0,
                    last_failure_at TIMESTAMP,
                    last_success_at TIMESTAMP,
                    is_disabled BOOLEAN DEFAULT 0,
                    disabled_at TIMESTAMP
                )
            """)
            
            # Scraper Stats table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scraper_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    council_id TEXT NOT NULL,
                    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    articles_found INTEGER DEFAULT 0,
                    articles_saved INTEGER DEFAULT 0,
                    status TEXT,
                    duration_ms INTEGER
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stats_council_run ON scraper_stats(council_id, run_at)")
            
            conn.commit()
    
    def article_exists(self, url: str) -> bool:
        """Check if an article URL has already been seen."""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,))
            return cursor.fetchone() is not None
            
    def is_posted(self, url: str) -> bool:
        """Check if an article has been posted."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM articles WHERE url = ? AND posted_at IS NOT NULL", 
                (url,)
            )
            return cursor.fetchone() is not None

    def add_article(self, article: Dict, state: str) -> int:
        """
        Add a new article to the database.
        
        Returns:
            ID of the inserted article, or existing ID if duplicate
        """
        with self._get_conn() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO articles (url, council_id, title, date, excerpt, state)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article['url'],
                        article['council_id'],
                        article['title'],
                        article['date'],
                        article['excerpt'],
                        state
                    )
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Article already exists, return its ID
                cursor = conn.execute("SELECT id FROM articles WHERE url = ?", (article['url'],))
                row = cursor.fetchone()
                return row['id'] if row else -1

    def add_articles_bulk(self, articles: List[Dict], state: str, status: str = 'new') -> int:
        """
        Add multiple articles to the database in a single transaction.
        Ignores duplicates (INSERT OR IGNORE).
        
        Returns:
            Number of new articles added.
        """
        if not articles:
            return 0
            
        with self._get_conn() as conn:
            # Prepare data for executemany
            data = [
                (
                    a['url'],
                    a['council_id'],
                    a['title'],
                    a['date'],
                    a['excerpt'],
                    state,
                    status
                )
                for a in articles
            ]
            
            # Use INSERT OR IGNORE to handle duplicates gracefully in bulk
            cursor = conn.executemany(
                """
                INSERT OR IGNORE INTO articles (url, council_id, title, date, excerpt, state, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                data
            )
            conn.commit()
            return cursor.rowcount

    def mark_as_posted(self, url: str, handle: str):
        """Mark an article as posted."""
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE articles 
                SET posted_at = CURRENT_TIMESTAMP, posted_to_handle = ?
                WHERE url = ?
                """,
                (handle, url)
            )
            conn.commit()

    def get_unposted_articles(self, state: str, limit: int = 50) -> List[Dict]:
        """
        Get unposted articles for a specific state.
        
        Implements variety logic to prevent consecutive posts from the same council
        unless necessary.
        """
        # Fetch a larger batch to allow for reordering
        fetch_limit = max(limit * 5, 200)
        
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM articles 
                WHERE state = ? AND posted_at IS NULL AND status != 'archived'
                ORDER BY first_seen_at DESC
                LIMIT ?
                """,
                (state, fetch_limit)
            )
            raw_articles = [dict(row) for row in cursor.fetchall()]
            
        if not raw_articles:
            return []
            
        # Group by council
        council_queues = {}
        council_order = [] # To maintain priority based on recency
        
        for article in raw_articles:
            c_id = article['council_id']
            if c_id not in council_queues:
                council_queues[c_id] = []
                council_order.append(c_id)
            council_queues[c_id].append(article)
            
        # Round robin selection
        varied_articles = []
        while len(varied_articles) < limit and any(council_queues.values()):
            # Iterate through councils in order of their newest article
            for c_id in council_order:
                if council_queues[c_id]:
                    varied_articles.append(council_queues[c_id].pop(0))
                    if len(varied_articles) >= limit:
                        break
                        
        return varied_articles

    def get_council_health(self, council_id: str) -> Dict:
        """Get health status for a council."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM council_health WHERE council_id = ?", 
                (council_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {
                'council_id': council_id,
                'consecutive_failures': 0,
                'is_disabled': 0
            }

    def record_success(self, council_id: str):
        """Record a successful scrape."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO council_health (council_id, consecutive_failures, last_success_at, is_disabled)
                VALUES (?, 0, CURRENT_TIMESTAMP, 0)
                ON CONFLICT(council_id) DO UPDATE SET
                    consecutive_failures = 0,
                    last_success_at = CURRENT_TIMESTAMP,
                    is_disabled = 0,
                    disabled_at = NULL
            """, (council_id,))
            conn.commit()

    def record_failure(self, council_id: str) -> bool:
        """
        Record a failed scrape.
        Returns True if the council is now disabled.
        """
        with self._get_conn() as conn:
            # Get current failures
            cursor = conn.execute(
                "SELECT consecutive_failures FROM council_health WHERE council_id = ?", 
                (council_id,)
            )
            row = cursor.fetchone()
            current_failures = row['consecutive_failures'] if row else 0
            new_failures = current_failures + 1
            
            is_disabled = 1 if new_failures >= 5 else 0
            disabled_at = datetime.now() if is_disabled else None
            
            conn.execute("""
                INSERT INTO council_health (council_id, consecutive_failures, last_failure_at, is_disabled, disabled_at)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)
                ON CONFLICT(council_id) DO UPDATE SET
                    consecutive_failures = ?,
                    last_failure_at = CURRENT_TIMESTAMP,
                    is_disabled = ?,
                    disabled_at = ?
            """, (council_id, new_failures, is_disabled, disabled_at, new_failures, is_disabled, disabled_at))
            conn.commit()
            
            return is_disabled == 1

    def log_scraper_run(self, council_id: str, articles_found: int, status: str, duration_ms: int, articles_saved: int = 0):
        """Log a scraper run execution."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO scraper_stats (council_id, articles_found, articles_saved, status, duration_ms)
                VALUES (?, ?, ?, ?, ?)
            """, (council_id, articles_found, articles_saved, status, duration_ms))
            conn.commit()
            
    def get_stats(self, state: str) -> Dict:
        """Get statistics for a state."""
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as c FROM articles WHERE state = ?", 
                (state,)
            ).fetchone()['c']
            
            posted = conn.execute(
                "SELECT COUNT(*) as c FROM articles WHERE state = ? AND posted_at IS NOT NULL", 
                (state,)
            ).fetchone()['c']
            
            return {
                "total_articles": total,
                "posted_articles": posted,
                "backlog": total - posted
            }

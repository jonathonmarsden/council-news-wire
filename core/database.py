"""
Database module for Council News Bot.

Handles SQLite database operations for tracking scraped articles and posting history.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Set, Tuple

class Database:
    """SQLite database handler."""
    
    def __init__(self, db_path: str = "bot.db"):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize the database schema."""
        with self._get_conn() as conn:
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
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    posted_at TIMESTAMP,
                    posted_to_handle TEXT
                )
            """)
            
            # Create index for faster lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON articles(url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_state_posted ON articles(state, posted_at)")
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
                WHERE state = ? AND posted_at IS NULL
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

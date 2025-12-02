import sqlite3
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Database

def strict_cleanup():
    db = Database()
    with db._get_conn() as conn:
        print("Running STRICT cleanup...")
        
        # Delete unposted articles older than 7 days
        # This aligns the DB with the scraper's MAX_ARTICLE_AGE_DAYS = 7 policy
        cursor = conn.execute("DELETE FROM articles WHERE posted_at IS NULL AND date < date('now', '-7 days')")
        print(f"Deleted {cursor.rowcount} stale articles (> 7 days old).")
        
        conn.commit()
        
        # Verify remaining
        cursor = conn.execute("SELECT COUNT(*) FROM articles WHERE posted_at IS NULL")
        remaining = cursor.fetchone()[0]
        print(f"Remaining backlog: {remaining} articles.")

if __name__ == "__main__":
    strict_cleanup()

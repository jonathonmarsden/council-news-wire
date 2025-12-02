import sqlite3
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from core.database import Database

def cleanup_stale_backlog():
    db = Database()
    with db._get_conn() as conn:
        print("Cleaning up stale backlog...")
        
        # 1. Delete 'legacy-migration' articles (177)
        cursor = conn.execute("DELETE FROM articles WHERE council_id = 'legacy-migration'")
        print(f"Deleted {cursor.rowcount} 'legacy-migration' articles.")
        
        # 2. Delete articles older than 30 days that haven't been posted
        cursor = conn.execute("DELETE FROM articles WHERE posted_at IS NULL AND date < date('now', '-30 days')")
        print(f"Deleted {cursor.rowcount} articles older than 30 days.")
        
        # 3. Delete undated articles (likely bad scrapes)
        # Be careful not to delete freshly scraped ones that might just be missing a date parser
        # But for now, if it has no date, we can't trust it to be 'news'
        cursor = conn.execute("DELETE FROM articles WHERE posted_at IS NULL AND (date IS NULL OR date = '')")
        print(f"Deleted {cursor.rowcount} undated articles.")
        
        conn.commit()
        
        # Verify remaining
        cursor = conn.execute("SELECT COUNT(*) FROM articles WHERE posted_at IS NULL")
        remaining = cursor.fetchone()[0]
        print(f"Remaining backlog: {remaining} articles.")

if __name__ == "__main__":
    cleanup_stale_backlog()

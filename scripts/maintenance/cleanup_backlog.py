import sys
import os
from sqlalchemy import text

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from core.database import Database

def cleanup_stale_backlog():
    db = Database()
    with db.get_session() as session:
        print("Cleaning up stale backlog...")
        
        # 1. Delete 'legacy-migration' articles (177)
        result = session.execute(text("DELETE FROM articles WHERE council_id = 'legacy-migration'"))
        print(f"Deleted {result.rowcount} 'legacy-migration' articles.")
        
        # 2. Delete articles older than 30 days that haven't been posted
        # Use Python to generate key for string comparison (works on both DBs if ISO format)
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
        result = session.execute(
            text("DELETE FROM articles WHERE posted_at IS NULL AND date < :cutoff"),
            {"cutoff": cutoff}
        )
        print(f"Deleted {result.rowcount} articles older than 30 days.")
        
        # 3. Delete undated articles (likely bad scrapes)
        result = session.execute(text("DELETE FROM articles WHERE posted_at IS NULL AND (date IS NULL OR date = '')"))
        print(f"Deleted {result.rowcount} undated articles.")
        
        session.commit()
        
        # Verify remaining
        result = session.execute(text("SELECT COUNT(*) FROM articles WHERE posted_at IS NULL"))
        remaining = result.scalar()
        print(f"Remaining backlog: {remaining} articles.")

if __name__ == "__main__":
    cleanup_stale_backlog()

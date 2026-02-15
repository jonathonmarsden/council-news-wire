import sys
import os
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.database import Database

def strict_cleanup():
    db = Database()
    with db.get_session() as session:
        print("Running STRICT cleanup...")
        
        # Delete unposted articles older than 7 days
        # This aligns the DB with the scraper's MAX_ARTICLE_AGE_DAYS = 7 policy
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        result = session.execute(
            text("DELETE FROM articles WHERE posted_at IS NULL AND date < :cutoff"),
            {"cutoff": cutoff}
        )
        print(f"Deleted {result.rowcount} stale articles (> 7 days old).")
        
        session.commit()
        
        # Verify remaining
        result = session.execute(text("SELECT COUNT(*) FROM articles WHERE posted_at IS NULL"))
        remaining = result.scalar()
        print(f"Remaining backlog: {remaining} articles.")

if __name__ == "__main__":
    strict_cleanup()

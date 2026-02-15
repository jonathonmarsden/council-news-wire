import sys
import os
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from core.constants import GARBAGE_TITLES
from core.database import Database

def cleanup_malformed_posts():
    db = Database()
    print("Connecting to Database (PostgreSQL)...")
    
    with db.get_session() as session:
        # 1. Archive articles from the future (Year > 2027)
        # We must NOT delete them, otherwise the scraper will re-discover them and repost them (Infinite Loop).
        print("Scanning for future dates (Archiving)...")
        result = session.execute(text("UPDATE articles SET status = 'archived', posted_at = NOW() WHERE date > '2027-01-01' AND status != 'archived'"))
        if result.rowcount > 0:
            print(f"Archived {result.rowcount} future rows.")

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
        
    print("Cleanup complete on PostgreSQL.")

if __name__ == "__main__":
    cleanup_malformed_posts()
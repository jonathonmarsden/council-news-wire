import sqlite3
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Database

def cleanup_inner_west():
    db = Database()
    with db._get_conn() as conn:
        # Count before
        cursor = conn.execute("SELECT COUNT(*) FROM articles WHERE council_id = 'inner-west-council' AND (date IS NULL OR date = '' OR date = 'None')")
        count = cursor.fetchone()[0]
        print(f"Found {count} undated Inner West articles to delete.")
        
        if count > 0:
            # Delete
            conn.execute("DELETE FROM articles WHERE council_id = 'inner-west-council' AND (date IS NULL OR date = '' OR date = 'None')")
            conn.commit()
            print("Deletion complete.")
            
            # Verify
            cursor = conn.execute("SELECT COUNT(*) FROM articles WHERE council_id = 'inner-west-council'")
            remaining = cursor.fetchone()[0]
            print(f"Remaining Inner West articles: {remaining}")
        else:
            print("Nothing to delete.")

if __name__ == "__main__":
    cleanup_inner_west()

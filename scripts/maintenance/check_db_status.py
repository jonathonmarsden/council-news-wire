import sqlite3
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from core.config import DB_PATH

def check_status():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)
        
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    # Count total articles
    c.execute("SELECT COUNT(*) FROM articles")
    total = c.fetchone()[0]
    
    # Count unposted articles (excluding archived)
    c.execute("SELECT COUNT(*) FROM articles WHERE posted_at IS NULL AND status != 'archived'")
    unposted = c.fetchone()[0]
    
    # Get breakdown by council for unposted
    c.execute("""
        SELECT council_id, COUNT(*) 
        FROM articles 
        WHERE posted_at IS NULL AND status != 'archived'
        GROUP BY council_id 
        ORDER BY COUNT(*) DESC
    """)
    breakdown = c.fetchall()
    
    print(f"Total Articles: {total}")
    print(f"Unposted (Backlog): {unposted}")
    print("\nBacklog by Council:")
    for council, count in breakdown:
        print(f"  {council}: {count}")

if __name__ == "__main__":
    check_status()

#!/usr/bin/env python3
"""
Archive Old Articles Script

Marks unposted articles older than 30 days as 'archived' to prevent posting stale news.
This fixes the issue where initial scrapes might have grabbed years of history.
"""

import sys
import os
import sqlite3
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.config import DB_PATH

def archive_old_articles(days=30):
    """Archive articles older than `days`."""
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    print(f"Archiving unposted articles older than {cutoff_date}...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check count first
    cursor.execute("""
        SELECT count(*), council_id 
        FROM articles 
        WHERE posted_at IS NULL 
        AND status != 'archived' 
        AND date < ?
        GROUP BY council_id
        ORDER BY count(*) DESC
    """, (cutoff_date,))
    
    results = cursor.fetchall()
    
    if not results:
        print("No old articles found to archive.")
        return
        
    print("\nFound old articles to archive:")
    total_to_archive = 0
    for count, council in results:
        print(f"  {council}: {count}")
        total_to_archive += count
        
    if input(f"\nProceed to archive {total_to_archive} articles? (y/n): ").lower() != 'y':
        print("Aborted.")
        return

    # Execute update
    cursor.execute("""
        UPDATE articles 
        SET status = 'archived' 
        WHERE posted_at IS NULL 
        AND status != 'archived' 
        AND date < ?
    """, (cutoff_date,))
    
    conn.commit()
    print(f"\nSuccessfully archived {cursor.rowcount} articles.")
    conn.close()

if __name__ == "__main__":
    # Default to 30 days to be safe, but for the backlog issue we saw (2018), this is perfect.
    archive_old_articles(days=30)

import sqlite3
import os
import sys
import argparse

# Add project root to path
sys.path.append(os.getcwd())

from core.config import DB_PATH

def cleanup_html_titles(dry_run=True):
    print(f"Checking database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Look for titles OR excerpts with HTML tags or entities
    # We check for <, >, &lt;, &gt;, &nbsp;, &amp;
    query = """
    SELECT id, council_id, title, url, posted_at, status, excerpt
    FROM articles 
    WHERE (
           title LIKE '%<%' 
        OR title LIKE '%>%'
        OR title LIKE '%&lt;%'
        OR title LIKE '%&gt;%'
        OR title LIKE '%&nbsp;%'
        OR title LIKE '%&amp;%'
        OR title LIKE '%&#%'
        OR excerpt LIKE '%<%' 
        OR excerpt LIKE '%>%'
        OR excerpt LIKE '%&lt;%'
        OR excerpt LIKE '%&gt;%'
        OR excerpt LIKE '%&nbsp;%'
        OR excerpt LIKE '%&amp;%'
        OR excerpt LIKE '%&#%'
    )
    AND state = 'wa'
    ORDER BY posted_at DESC
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} WA articles with potential HTML in title or excerpt:")
    
    ids_to_delete = []
    
    for row in rows:
        print(f"ID: {row['id']}")
        print(f"Council: {row['council_id']}")
        print(f"Title: {row['title']}")
        print(f"Excerpt: {row['excerpt']}")
        print(f"URL: {row['url']}")
        print(f"Posted At: {row['posted_at']}")
        print("-" * 40)
        ids_to_delete.append(row['id'])
        
    if not ids_to_delete:
        print("No articles found to clean up.")
        conn.close()
        return

    if dry_run:
        print(f"\n[DRY RUN] Would delete {len(ids_to_delete)} articles.")
        print("Run with --force to actually delete.")
    else:
        print(f"\nDeleting {len(ids_to_delete)} articles...")
        placeholders = ','.join('?' for _ in ids_to_delete)
        cursor.execute(f"DELETE FROM articles WHERE id IN ({placeholders})", ids_to_delete)
        conn.commit()
        print("Done.")
        
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Cleanup articles with HTML in titles')
    parser.add_argument('--force', action='store_true', help='Actually delete the articles')
    args = parser.parse_args()
    
    cleanup_html_titles(dry_run=not args.force)

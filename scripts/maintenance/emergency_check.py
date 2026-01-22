import sqlite3
import os
import sys
import json

# Add parent dir to path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = '/opt/council-news-bot/data/bot.db'
if not os.path.exists(DB_PATH):
    # Fallback for local
    DB_PATH = 'data/bot.db'

def check_recent_posts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Correct Schema: 
    # id, url, council_id, title, date, excerpt, state, first_seen_at, posted_at, posted_to_handle, status
    
    print("Checking recent 50 WA articles (by ID DESC)...")
    
    query = """
    SELECT id, council_id, title, date, status, posted_at, state, first_seen_at
    FROM articles 
    WHERE length(title) < 10 OR title GLOB '*[0-9][0-9]*'
    ORDER BY id DESC 
    LIMIT 50
    """
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        
        print(f"{'ID':<8} | {'State':<5} | {'Council':<25} | {'First Seen':<16} | {'Status':<8} | Title")
        print("-" * 120)
        for row in rows:
            aid, cid, title, date, status, posted_at, state, created_at = row
            # Clean newlines from title
            if title:
                title = title.replace('\n', ' ').strip()
            # ... rest of code
            
            # Simple check for potential garbage
            is_suspicious = False
            if len(title) < 5 or title.isdigit() or len(title) > 200:
                is_suspicious = True
            
            prefix = "   "
            if is_suspicious:
                 prefix = ">>>"
            
            print(f"{prefix} {aid:<8} | {state:<5} | {cid:<25} | {str(created_at)[:16]:<16} | {status:<8} | {title[:50]}...")

    except Exception as e:
        print(f"Error: {e}")

    conn.close()

if __name__ == "__main__":
    check_recent_posts()

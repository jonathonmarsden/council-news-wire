import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.database import Database

def reset_act_posts():
    # Inside container, DB is at /app/bot.db
    # On host, it is at /opt/council-news-bot/bot.db
    # We try to detect or just use the relative path if running from root
    db_path = 'bot.db'
    
    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Find ALL ACT articles
    cursor.execute("""
        SELECT id, title, url, posted_at, status, state
        FROM articles 
        WHERE state = 'ACT' OR state = 'act'
        ORDER BY id DESC
    """)
    
    articles = cursor.fetchall()
    
    if not articles:
        print("No ACT articles found in DB.")
        return

    print(f"Found {len(articles)} ACT articles:")
    for art in articles:
        print(f"[{art['id']}] {art['title']} (State: {art['state']}, Status: {art['status']}, Posted: {art['posted_at']})")

        
    # Do not reset yet, just list
    conn.close()
    conn.close()

if __name__ == "__main__":
    reset_act_posts()

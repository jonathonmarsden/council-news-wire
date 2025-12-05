import os
import sys
import sqlite3
from datetime import datetime, timedelta, timezone
from atproto import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_PATH = 'bot.db'
BSKY_HANDLE = os.getenv('BLUESKY_HANDLE_WA')
BSKY_PASSWORD = os.getenv('BLUESKY_PASSWORD_WA')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def cleanup_wa_recent():
    print("--- Starting Cleanup of Recent WA Posts (Last 3 Hours) ---")
    
    # 1. Identify and Delete from Database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Debug: Check recent posts regardless of state
    print("Debug: Checking most recent 5 posts in DB...")
    cursor.execute("SELECT title, state, posted_at FROM articles ORDER BY posted_at DESC LIMIT 5")
    for row in cursor.fetchall():
        print(f"  [{row['state']}] {row['posted_at']} - {row['title']}")

    # Calculate cutoff time (3 hours ago)
    # SQLite uses UTC usually, check if posted_at is UTC. 
    # Assuming CURRENT_TIMESTAMP is UTC.
    cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"Looking for WA articles posted after {cutoff_time}...")
    
    cursor.execute("""
        SELECT id, council_id, title, url, posted_at 
        FROM articles 
        WHERE state = 'wa' 
        AND posted_at > datetime('now', '-3 hours')
    """)
    
    articles = cursor.fetchall()
    print(f"Found {len(articles)} articles in DB.")
    
    deleted_count = 0
    for article in articles:
        print(f"Deleting from DB: [{article['council_id']}] {article['title']}")
        cursor.execute("DELETE FROM articles WHERE id = ?", (article['id'],))
        deleted_count += 1
        
    conn.commit()
    print(f"Deleted {deleted_count} records from database.")
    
    # 2. Delete from BlueSky
    if not BSKY_HANDLE or not BSKY_PASSWORD:
        print("Error: BlueSky credentials not found in environment.")
        return

    print(f"\nConnecting to BlueSky as {BSKY_HANDLE}...")
    client = Client()
    client.login(BSKY_HANDLE, BSKY_PASSWORD)
    
    # Get author feed
    # limit to 50 posts, should be enough for 3 hours
    feed = client.app.bsky.feed.get_author_feed({'actor': BSKY_HANDLE, 'limit': 50})
    
    print(f"Fetched {len(feed.feed)} posts from feed.")
    
    bsky_deleted_count = 0
    now = datetime.now(timezone.utc)
    
    for item in feed.feed:
        post = item.post
        record = post.record
        
        # Parse created_at
        # Format: 2025-12-04T20:35:45.360Z
        created_at_str = record.created_at.replace('Z', '+00:00')
        try:
            created_at = datetime.fromisoformat(created_at_str)
        except ValueError:
            # Handle other formats if necessary
            continue
            
        # Check age
        age = now - created_at
        if age > timedelta(hours=3):
            continue
            
        # Check if it's a WA post
        text = record.text
        if '#WACouncils' in text or '#WALGA' in text:
            print(f"Deleting from Bsky: {text[:50]}... (Age: {age})")
            client.delete_post(post.uri)
            bsky_deleted_count += 1
        else:
            print(f"Skipping non-WA post: {text[:50]}...")
            
    print(f"Deleted {bsky_deleted_count} posts from BlueSky.")
    print("\nCleanup complete.")

if __name__ == "__main__":
    cleanup_wa_recent()

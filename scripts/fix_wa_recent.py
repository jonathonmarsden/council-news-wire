import os
from datetime import datetime, timedelta, timezone
from atproto import Client
from dotenv import load_dotenv
from sqlalchemy import select

from core.database import Database
from core.models import Article

# Load environment variables
load_dotenv()

BSKY_HANDLE = os.getenv('BLUESKY_HANDLE_WA')
BSKY_PASSWORD = os.getenv('BLUESKY_PASSWORD_WA')

def cleanup_wa_recent():
    print("--- Starting Cleanup of Recent WA Posts (Last 3 Hours) ---")
    
    # 1. Identify and Delete from Database
    db = Database()
    session = db.get_session()
    
    # Debug: Check recent posts regardless of state
    print("Debug: Checking most recent 5 posts in DB...")
    recent_stmt = select(
        Article.title,
        Article.state,
        Article.posted_at
    ).order_by(Article.posted_at.desc()).limit(5)
    for row in session.execute(recent_stmt).all():
        print(f"  [{row[1]}] {row[2]} - {row[0]}")

    # Calculate cutoff time (3 hours ago)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=3)

    print(f"Looking for WA articles posted after {cutoff_time}...")

    wa_stmt = select(Article).where(
        Article.state == 'wa',
        Article.posted_at > cutoff_time
    )
    articles = session.execute(wa_stmt).scalars().all()
    print(f"Found {len(articles)} articles in DB.")
    
    deleted_count = 0
    for article in articles:
        print(f"Deleting from DB: [{article.council_id}] {article.title}")
        session.delete(article)
        deleted_count += 1

    session.commit()
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

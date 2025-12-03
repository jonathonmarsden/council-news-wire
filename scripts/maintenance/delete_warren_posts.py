
import os
import sys
import sqlite3
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from atproto import Client

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.database import Database

def delete_malformed_warren_posts():
    # Load environment variables
    load_dotenv()
    
    handle = os.getenv("BLUESKY_HANDLE_NSW")
    password = os.getenv("BLUESKY_PASSWORD_NSW")
    
    if not handle or not password:
        print("Error: BLUESKY_HANDLE_NSW or BLUESKY_PASSWORD_NSW not found in environment.")
        return

    print(f"Authenticating as {handle}...")
    client = Client()
    client.login(handle, password)
    
    # Connect to DB
    db_path = "bot.db"
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Fetching recent posts...")
    # Get author feed
    feed = client.get_author_feed(actor=handle, limit=100)
    
    deleted_count = 0
    repost_queue = []
    
    for feed_view in feed.feed:
        post = feed_view.post
        record = post.record
        text = record.text
        
        # Check if it's a Warren Shire post
        # The bot usually posts with hashtags, e.g. #WarrenShireCouncil
        if "#WarrenShireCouncil" not in text and "Warren Shire Council" not in text:
            continue
            
        # Check for malformed indicators
        is_malformed = False
        
        # 1. Starts with "Media Release:"
        if text.startswith("Media Release:") or text.startswith("Press Release:"):
            is_malformed = True
            
        # 2. Check for date suffix pattern in the text
        # e.g. "Title27 November 2025" -> "e27 November"
        # e.g. "202530 January" -> "530 January"
        if re.search(r'[a-z]\d{1,2}\s+[A-Za-z]+\s+\d{4}', text):
            is_malformed = True
        elif re.search(r'\d{4}\d{1,2}\s+[A-Za-z]+', text):
            is_malformed = True
            
        # 3. Check against DB title if URL is found
        url = None
        if hasattr(record, 'facets') and record.facets:
            for facet in record.facets:
                for feature in facet.features:
                    if hasattr(feature, 'uri'):
                        url = feature.uri
                        break
                if url: break
        
        if not url:
            match = re.search(r'https?://[^\s]+', text)
            if match:
                url = match.group(0)
                
        if url and not is_malformed:
            # Check if DB has a cleaner title
            cursor.execute("SELECT title FROM articles WHERE url = ?", (url,))
            row = cursor.fetchone()
            if row:
                clean_title = row[0]
                # If the post text starts with the clean title but has extra chars immediately after
                if text.startswith(clean_title):
                    remainder = text[len(clean_title):]
                    # If remainder starts with a digit or date-like char without space
                    if remainder and remainder[0].isdigit():
                        print(f"Detected malformed suffix for {clean_title}: '{remainder[:10]}...'")
                        is_malformed = True
                else:
                    # Debug why it didn't match
                    # print(f"Title mismatch: DB='{clean_title}' vs Post='{text[:len(clean_title)+10]}'")
                    pass

        if is_malformed:
            print(f"Found malformed post: {text[:50]}...")
            print(f"URL: {url}")
            
            # Delete post
            print(f"Deleting post {post.uri}...")
            client.delete_post(post.uri)
            deleted_count += 1
            
            # Mark for reposting
            if url:
                repost_queue.append(url)
        else:
            print(f"Skipping likely clean post: {text[:50]}...")

    print(f"Deleted {deleted_count} posts.")
    
    # Reset posted_at in DB
    if repost_queue:
        print(f"Resetting {len(repost_queue)} articles in database for reposting...")
        placeholders = ','.join(['?'] * len(repost_queue))
        cursor.execute(f"UPDATE articles SET posted_at = NULL WHERE url IN ({placeholders})", repost_queue)
        conn.commit()
        print("Database updated.")
    
    conn.close()

if __name__ == "__main__":
    delete_malformed_warren_posts()

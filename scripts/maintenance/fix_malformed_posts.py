import sys
import os
import sqlite3
from atproto import Client, models
from dotenv import load_dotenv

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Database

def load_state_config(state_code):
    import json
    with open(f"states/{state_code.lower()}/config.json", 'r') as f:
        return json.load(f)

def reset_article_in_db(db, title_fragment):
    """Find article by title fragment and reset posted status."""
    conn = db._get_conn()
    cursor = conn.cursor()
    
    # Try to find the article
    # The title in the post might be truncated or have extra formatting
    # We'll try to match the start of the title
    
    # Clean up the fragment (remove "📰 council" prefix if present)
    clean_fragment = title_fragment
    if "📰" in clean_fragment:
        parts = clean_fragment.split('\n\n')
        if len(parts) > 1:
            clean_fragment = parts[1] # The title is usually the second block
    
    clean_fragment = clean_fragment.strip().split('\n')[0] # Take first line
    if len(clean_fragment) > 50:
        clean_fragment = clean_fragment[:50] # Truncate for search
        
    print(f"Searching DB for title like: {clean_fragment}%")
    
    cursor.execute("SELECT id, title, url FROM articles WHERE title LIKE ?", (f"{clean_fragment}%",))
    results = cursor.fetchall()
    
    if not results:
        print("❌ No matching article found in DB.")
        return False
    
    if len(results) > 1:
        print(f"⚠️ Found {len(results)} matches. Resetting all.")
        
    for row in results:
        print(f"  Resetting: {row['title']} ({row['url']})")
        cursor.execute("UPDATE articles SET posted_at = NULL, posted_to_handle = NULL WHERE id = ?", (row['id'],))
    
    conn.commit()
    return True

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 fix_malformed_posts.py <state> <count>")
        sys.exit(1)
        
    state = sys.argv[1].lower()
    count = int(sys.argv[2])
    
    load_dotenv()
    config = load_state_config(state)
    
    handle = os.environ.get(config['bluesky_handle_env'])
    password = os.environ.get(config['bluesky_password_env'])
    
    if not handle or not password:
        print(f"Missing credentials for {state}")
        sys.exit(1)
        
    print(f"Connecting to {handle}...")
    client = Client()
    client.login(handle, password)
    
    db = Database()
    
    print(f"Fetching last {count} posts...")
    feed = client.get_author_feed(actor=handle, limit=count)
    
    for item in feed.feed:
        post = item.post
        uri = post.uri
        text = post.record.text
        
        print(f"\nProcessing post: {uri}")
        print(f"Text: {text[:100]}...")
        
        # Reset in DB
        reset_article_in_db(db, text)
        
        # Delete from BlueSky
        print("Deleting from BlueSky...")
        client.delete_post(post.uri)
        print("✅ Deleted.")

if __name__ == "__main__":
    main()

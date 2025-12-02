import os
import sys
import re
import time
from datetime import datetime
from dotenv import load_dotenv
from atproto import Client

# Load environment variables
load_dotenv()

def parse_date(text):
    """Extract and parse date from post text."""
    # Supports formats:
    # "Published: 28 November 2025"
    # "28 Nov 2025"
    # "26 November 2025"
    
    # Regex for Day Month(full or short) Year
    # Captures: (Day) (Month) (Year)
    pattern = r'\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b'
    
    matches = re.finditer(pattern, text)
    
    for match in matches:
        day, month_str, year = match.groups()
        
        # Try full month name (e.g. November)
        try:
            return datetime.strptime(f"{day} {month_str} {year}", "%d %B %Y")
        except ValueError:
            pass
            
        # Try short month name (e.g. Nov)
        try:
            return datetime.strptime(f"{day} {month_str} {year}", "%d %b %Y")
        except ValueError:
            pass
            
    return None

def main():
    handle = os.getenv('BLUESKY_HANDLE')
    password = os.getenv('BLUESKY_PASSWORD')
    
    if not handle or not password:
        print("Error: BLUESKY_HANDLE and BLUESKY_PASSWORD must be set.")
        return

    print(f"Connecting to BlueSky as {handle}...")
    client = Client()
    try:
        client.login(handle, password)
    except Exception as e:
        print(f"Failed to login: {e}")
        return

    print("Fetching posts...")
    
    cursor = None
    all_posts = []
    
    # Fetch all posts (limit to 2000 to be safe, though likely fewer)
    while True:
        feed = client.get_author_feed(actor=client.me.did, limit=100, cursor=cursor)
        all_posts.extend(feed.feed)
        
        if not feed.cursor:
            break
            
        cursor = feed.cursor
        print(f"Fetched {len(all_posts)} posts so far...")
        
        if len(all_posts) > 2000:
            break
    
    print(f"Total posts fetched: {len(all_posts)}")
    
    cutoff_date = datetime(2025, 1, 1)
    posts_to_delete = []
    
    print(f"Scanning for posts dated before {cutoff_date.strftime('%Y-%m-%d')}...")
    
    for feed_view in all_posts:
        post = feed_view.post
        record = post.record
        text = record.text
        
        post_date = parse_date(text)
        
        if post_date:
            # Debug: print first few dates found
            if len(all_posts) < 5: 
                print(f"Debug: Parsed date {post_date} from text start: {text[:20]}...")
                
            if post_date < cutoff_date:
                # Get title (first line)
                title = text.splitlines()[0] if text else "No Title"
                print(f"Found old post ({post_date.strftime('%Y-%m-%d')}): {title[:60]}...")
                posts_to_delete.append(post)
        # else:
            # print(f"Skipping post with no date: {text.splitlines()[0][:30]}...")

    print(f"\nFound {len(posts_to_delete)} posts to delete.")
    
    if not posts_to_delete:
        print("No posts to delete.")
        return

    if '--force' in sys.argv:
        confirm = 'y'
    else:
        confirm = input("Delete these posts? (y/n): ")
    
    if confirm.lower() == 'y':
        deleted_count = 0
        for post in posts_to_delete:
            try:
                client.delete_post(post.uri)
                # print(f"Deleted: {post.uri}")
                deleted_count += 1
                if deleted_count % 10 == 0:
                    print(f"Deleted {deleted_count} posts...")
                time.sleep(0.1) # Rate limit niceness
            except Exception as e:
                print(f"Failed to delete {post.uri}: {e}")
        print(f"Finished. Deleted {deleted_count} posts.")
    else:
        print("Operation cancelled.")

if __name__ == "__main__":
    main()

import os
import sys
from dotenv import load_dotenv
from atproto import Client

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_saved_posts():
    load_dotenv()
    
    handle = os.environ.get('BLUESKY_HANDLE_ADMIN')
    password = os.environ.get('BLUESKY_PASSWORD_ADMIN')
    
    if not handle or not password:
        print("Error: Admin credentials not found in .env")
        return

    print(f"Logging in as {handle}...")
    client = Client()
    client.login(handle, password)
    
    print("Fetching bookmarks...")
    # Note: The method to get bookmarks depends on the SDK version.
    # Attempting standard approach.
    try:
        response = client.app.bsky.feed.get_actor_likes({'actor': handle}) 
        # Wait, user said "saved posts", which usually means bookmarks, not likes.
        # But bookmarks are private. If I am logged in as the user, I can see them.
        # Let's try to find the bookmark method.
        # In atproto, it's often app.bsky.graph.get_list or similar, but bookmarks are specific.
        # Let's try the direct lexicon call if the helper isn't obvious.
        
        # Actually, let's try to list recent posts from the QLD bot first to see duplicates publicly
        # if bookmarks fail. But let's try bookmarks first.
        
        # Using com.atproto.repo.list_records for bookmarks
        bookmarks = client.com.atproto.repo.list_records({
            'repo': client.me.did,
            'collection': 'app.bsky.feed.post', # This lists posts created by user.
            # Bookmarks are not records in the repo in the same way.
            # They are often private preferences.
        })
        
        # Let's try to just get the QLD feed posts and look for duplicates there, 
        # as that might be easier than navigating the private bookmarks API blindly.
        # But the user specifically said "saved posts".
        
        # Let's try to get the timeline or author feed of the QLD bot.
        qld_handle = os.environ.get('BLUESKY_HANDLE_QLD')
        print(f"\nFetching recent posts from QLD Bot ({qld_handle})...")
        
        qld_feed = client.app.bsky.feed.get_author_feed({'actor': qld_handle, 'limit': 100})
        
        posts = []
        for feed_view in qld_feed.feed:
            post = feed_view.post
            record = post.record
            posts.append({
                'uri': post.uri,
                'cid': post.cid,
                'text': record.text,
                'created_at': record.created_at
            })
            
        print(f"Analyzed {len(posts)} posts from QLD feed.")
        
        # Check for duplicates in text
        seen_texts = {}
        duplicates = []
        
        for p in posts:
            # Simple check: exact text match
            # We might want to check for URL match inside text
            text = p['text']
            if text in seen_texts:
                duplicates.append((p, seen_texts[text]))
            else:
                seen_texts[text] = p
                
        if duplicates:
            print(f"\nFound {len(duplicates)} duplicate pairs in recent 100 posts:")
            for new, old in duplicates:
                print(f"\nDUPLICATE:")
                print(f"  Text: {new['text'][:100]}...")
                print(f"  1. {old['created_at']} ({old['uri']})")
                print(f"  2. {new['created_at']} ({new['uri']})")
        else:
            print("\nNo exact text duplicates found in the last 100 posts.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_saved_posts()

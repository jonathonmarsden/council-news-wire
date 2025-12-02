import os
import sys
from dotenv import load_dotenv
from atproto import Client

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def cleanup_qld_duplicates():
    load_dotenv()
    
    handle = os.environ.get('BLUESKY_HANDLE_QLD')
    password = os.environ.get('BLUESKY_PASSWORD_QLD')
    
    if not handle or not password:
        print("Error: QLD credentials not found in .env")
        return

    print(f"Logging in as {handle}...")
    client = Client()
    client.login(handle, password)
    
    print("Fetching recent posts...")
    # Get author feed
    feed = client.app.bsky.feed.get_author_feed({'actor': handle, 'limit': 100})
    
    posts = []
    for feed_view in feed.feed:
        post = feed_view.post
        record = post.record
        posts.append({
            'uri': post.uri,
            'cid': post.cid,
            'text': record.text,
            'created_at': record.created_at
        })
        
    print(f"Analyzed {len(posts)} posts.")
    
    # Identify duplicates
    # We keep the OLDEST post and delete the NEWER ones
    seen_texts = {}
    to_delete = []
    
    # Process from oldest to newest to identify the "original"
    # But the feed returns newest first.
    # So we iterate in reverse order (oldest first)
    
    for p in reversed(posts):
        text = p['text']
        if text in seen_texts:
            # This is a duplicate (since we already saw an older one)
            # Wait, if we iterate oldest to newest:
            # 1. Old post -> seen
            # 2. New post -> seen? Yes -> Delete New Post
            to_delete.append(p)
        else:
            seen_texts[text] = p
            
    print(f"Found {len(to_delete)} duplicates to delete.")
    
    if not to_delete:
        return

    print("Deleting duplicates...")
    for p in to_delete:
        print(f"Deleting: {p['text'][:50]}... ({p['created_at']})")
        try:
            # URI format: at://did:plc:xxx/app.bsky.feed.post/rkey
            # We need repo (did) and rkey
            uri_parts = p['uri'].split('/')
            rkey = uri_parts[-1]
            repo = uri_parts[2] # did:plc:xxx
            
            client.delete_post(post_uri=p['uri'])
            print("  Deleted.")
        except Exception as e:
            print(f"  Failed to delete: {e}")

if __name__ == "__main__":
    cleanup_qld_duplicates()

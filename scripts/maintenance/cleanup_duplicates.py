import os
import sys
import argparse
from dotenv import load_dotenv
from atproto import Client

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def cleanup_duplicates(state_code):
    load_dotenv()
    
    state_upper = state_code.upper()
    handle_env = f'BLUESKY_HANDLE_{state_upper}'
    password_env = f'BLUESKY_PASSWORD_{state_upper}'
    
    handle = os.environ.get(handle_env)
    password = os.environ.get(password_env)
    
    if not handle or not password:
        print(f"Error: Credentials for {state_upper} not found in .env ({handle_env}, {password_env})")
        return

    print(f"Logging in as {handle} ({state_upper})...")
    try:
        client = Client()
        client.login(handle, password)
    except Exception as e:
        print(f"Login failed: {e}")
        return
    
    print("Fetching recent posts...")
    # Get author feed
    try:
        feed = client.app.bsky.feed.get_author_feed({'actor': handle, 'limit': 100})
    except Exception as e:
        print(f"Failed to fetch feed: {e}")
        return
    
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
    # The feed returns newest first, so we iterate in reverse.
    
    for p in reversed(posts):
        text = p['text']
        if text in seen_texts:
            # This is a duplicate (since we already saw an older one)
            to_delete.append(p)
        else:
            seen_texts[text] = p
            
    print(f"Found {len(to_delete)} duplicates to delete.")
    
    if not to_delete:
        print("No duplicates found.")
        return

    print("Deleting duplicates...")
    for p in to_delete:
        print(f"Deleting: {p['text'][:50]}... ({p['created_at']})")
        try:
            client.delete_post(post_uri=p['uri'])
            print("  Deleted.")
        except Exception as e:
            print(f"  Failed to delete: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Cleanup duplicate BlueSky posts')
    parser.add_argument('--state', type=str, required=True, help='State code (VIC, NSW, QLD)')
    args = parser.parse_args()
    
    cleanup_duplicates(args.state)

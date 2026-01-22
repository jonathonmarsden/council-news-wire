import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from atproto import Client

load_dotenv()

TARGET_BOTS = [
    ('WA', 'roundupnewsbotwa'),
    ('NSW', 'roundupnewsbotnsw'),
    ('QLD', 'roundupnewsbotqld'),
    ('VIC', 'roundupnewsbotvic'),
    ('SA', 'roundupnewsbotsa'),
    ('TAS', 'roundupnewsbottas'),
    ('NT', 'roundupnewsbotnt')
]

def main():
    print("EMERGENCY DELETE: Parsing posts from the last 3 hours...")
    
    # 3 hours ago
    cutoff = datetime.now(timezone.utc) - timedelta(hours=3)
    print(f"Cutoff time (UTC): {cutoff}")
    
    for state, handle_base in TARGET_BOTS:
        handle = f"{handle_base}.bsky.social"
        env_handle = os.getenv(f"BLUESKY_HANDLE_{state}")
        env_pass = os.getenv(f"BLUESKY_PASSWORD_{state}")
        
        if not env_handle or not env_pass:
            print(f"Skipping {state} (no credentials)")
            continue
            
        try:
            client = Client()
            client.login(env_handle, env_pass)
            
            # Fetch recent posts (fetch enough to cover the time window)
            feed = client.get_author_feed(actor=client.me.did, limit=50)
            if not feed.feed:
                print(f"[{state}] No posts found.")
                continue
                
            print(f"\nProcessing {handle}...")
            deleted_count = 0
            
            for item in feed.feed:
                post = item.post
                uri = post.uri
                
                # Check time
                indexed_at = post.indexed_at
                # format: 2026-01-22T04:22:15.123Z
                try:
                    # Parse timestamp (handle Z for UTC)
                    dt = datetime.fromisoformat(indexed_at.replace('Z', '+00:00'))
                    
                    if dt > cutoff:
                        text = post.record.text.replace('\n', ' ')[:60]
                        print(f"  [DELETE] ({dt.strftime('%H:%M:%S')}) {text}...")
                        client.delete_post(uri)
                        deleted_count += 1
                except Exception as e:
                    print(f"  [ERROR] parsing post {uri}: {e}")
                    continue
            
            print(f"  -> Deleted {deleted_count} posts for {state}.")
                        
        except Exception as e:
            print(f"Error processing {state}: {e}")

if __name__ == "__main__":
    main()

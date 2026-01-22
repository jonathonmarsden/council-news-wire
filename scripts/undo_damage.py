import os
import re
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
    print("Undo Damage: Deleting posts made in the last 1 hour that look malformed...")
    
    # 1 hour ago
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    
    for state, handle_base in TARGET_BOTS:
        handle = f"{handle_base}.bsky.social"
        env_handle = os.getenv(f"BLUESKY_HANDLE_{state}")
        env_pass = os.getenv(f"BLUESKY_PASSWORD_{state}")
        
        if not env_handle or not env_pass:
            continue
            
        try:
            client = Client()
            client.login(env_handle, env_pass)
            
            # Fetch recent posts
            feed = client.get_author_feed(actor=client.me.did, limit=10)
            if not feed.feed:
                continue
                
            print(f"\nChecking {handle}...")
            for item in feed.feed:
                post = item.post
                
                # Check time
                indexed_at = post.indexed_at
                # format: 2026-01-22T04:22:15.123Z
                try:
                    dt = datetime.fromisoformat(indexed_at.replace('Z', '+00:00'))
                    if dt < cutoff:
                        continue
                except:
                    continue
                
                text = post.record.text
                uri = post.uri
                
                # Criteria for "Bad Post" created by our broken script:
                # 1. Council Name line contains hashtags (LGNewsRoundup etc)
                # 2. Duplicate hashtags
                
                lines = text.split('\n')
                is_bad = False
                
                # Check for "LGNewsRoundup" appearing in the middle of text (Council Name field)
                # Usually it should only be at the end.
                if len(lines) >= 2:
                    # If the line BEFORE the final hashtag line contains "LGNewsRoundup", it's bad
                    # Or if the text has "LGNewsRoundup" appearing twice?
                    if text.count("LGNewsRoundup") > 1:
                        is_bad = True
                    elif "LGNewsRoundup" in text and not text.strip().endswith("LGNewsRoundup"):
                        # If tags aren't at the end?
                        pass
                        
                    # Specific signature of the bug:
                    # Council line became: "LGNewsRoundup VLGA ..."
                    for line in lines:
                        if "LGNewsRoundup" in line and len(line) > 50 and "Council" in line:
                             # This catches "LGNewsRoundup ... Council ... #..."
                             is_bad = True
                             
                if is_bad:
                    print(f"  [DELETE] Found bad post: {text[:50]}...")
                    try:
                        client.delete_post(uri)
                        print("    -> Deleted.")
                    except Exception as e:
                        print(f"    -> Failed to delete: {e}")
                        
        except Exception as e:
            print(f"Error processing {state}: {e}")

if __name__ == "__main__":
    main()

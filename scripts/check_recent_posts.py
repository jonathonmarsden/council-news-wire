import os
from datetime import datetime
from dotenv import load_dotenv
from atproto import Client

load_dotenv()

# Bots involved in the recent run
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
    print("Checking recent posts for all bots...")
    
    for state, handle_base in TARGET_BOTS:
        handle = f"{handle_base}.bsky.social"
        env_handle = os.getenv(f"BLUESKY_HANDLE_{state}")
        env_pass = os.getenv(f"BLUESKY_PASSWORD_{state}")
        
        if not env_handle or not env_pass:
            continue
            
        try:
            client = Client()
            client.login(env_handle, env_pass)
            
            # Get author feed (latest posts)
            feed = client.get_author_feed(actor=client.me.did, limit=5)
            
            if not feed.feed:
                continue

            print(f"\n[{state}] Latest posts for {handle}:")
            
            for item in feed.feed:
                post = item.post
                text = post.record.text
                uri = post.uri
                # Check cleanliness
                is_malformed = False
                lines = text.split('\n')
                
                # Check if it looks like the ones we just made
                # They might have messed up Council Names like "LGNewsRoundup VLGA..."
                print(f"  ---\n  {text[:100]}...\n  URI: {uri}")
                
        except Exception as e:
            print(f"Error checking {state}: {e}")

if __name__ == "__main__":
    main()

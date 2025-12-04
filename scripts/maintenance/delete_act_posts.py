import os
import sys
from pathlib import Path
from atproto import Client

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

def delete_posts():
    # Load env vars
    load_dotenv()
    
    handle = os.environ.get("BLUESKY_HANDLE_ACT")
    password = os.environ.get("BLUESKY_PASSWORD_ACT")
    
    if not handle or not password:
        print("Error: ACT credentials not found in environment.")
        return

    print(f"Authenticating as {handle}...")
    client = Client()
    client.login(handle, password)
    
    # Post RKeys to delete
    rkeys = [
        "3m72w7oq3n42s",
        "3m72wizlo3q2u"
    ]
    
    # Resolve DID
    did = client.me.did
    print(f"DID: {did}")
    
    for rkey in rkeys:
        uri = f"at://{did}/app.bsky.feed.post/{rkey}"
        print(f"Deleting post: {uri}")
        try:
            client.delete_post(uri)
            print("  ✅ Deleted")
        except Exception as e:
            print(f"  ❌ Failed: {e}")

if __name__ == "__main__":
    delete_posts()

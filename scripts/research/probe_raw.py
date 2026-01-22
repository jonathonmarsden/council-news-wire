import os
import sys
import json
import requests
from dotenv import load_dotenv
from atproto import Client

# Add project root to path
root_dir = os.path.join(os.path.dirname(__file__), '../../')
sys.path.append(root_dir)

load_dotenv(os.path.join(root_dir, '.env'))

BSKY_HANDLE = os.getenv("BLUESKY_HANDLE_ADMIN")
BSKY_PASSWORD = os.getenv("BLUESKY_PASSWORD_ADMIN")

def probe_raw():
    print(f"Logging in as {BSKY_HANDLE}...")
    client = Client()
    client.login(BSKY_HANDLE, BSKY_PASSWORD)
    
    # Extract session details
    # client.me is usually profile, client._session might hold the session
    # Let's try to find the JWT
    
    access_token = None
    if hasattr(client, '_session'):
        access_token = client._session.access_jwt
    else:
        print("Could not find _session on client")
        return

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    print("\n--- Raw Request: app.bsky.actor.getPreferences ---")
    try:
        url = "https://bsky.social/xrpc/app.bsky.actor.getPreferences"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            print("Preferences Keys/Types:")
            if 'preferences' in data:
                for pref in data['preferences']:
                    print(f" - {pref.get('$type')}")
                    if 'saved' in json.dumps(pref).lower():
                        print("   >>> FOUND 'saved' keyword:", json.dumps(pref)[:200])
            else:
                print(data)
        else:
            print(f"Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Req failed: {e}")

    print("\n--- Raw Request: com.atproto.repo.describeRepo ---")
    try:
        url = "https://bsky.social/xrpc/com.atproto.repo.describeRepo"
        params = {"repo": client.me.did}
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            data = resp.json()
            print("Collections:")
            for col in data.get('collections', []):
                print(f" - {col}")
                if 'save' in col.lower() or 'book' in col.lower():
                     print(f"   !!! DISCOVERED SUSPICIOUS COLLECTION: {col} !!!")
        else:
            print(f"Error {resp.status_code}: {resp.text}")

    except Exception as e:
        print(f"Req failed: {e}")

    print("\n--- Raw Request: app.bsky.bookmark.getBookmarks ---")
    try:
        url = "https://bsky.social/xrpc/app.bsky.bookmark.getBookmarks"
        resp = requests.get(url, headers=headers, params={"limit": 10})
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
             print(resp.json())
        else:
             print(resp.text)
    except Exception as e:
        print(f"Req failed: {e}")

    print("\n--- Raw Request: app.bsky.bookmark.listBookmarks ---")
    try:
        url = "https://bsky.social/xrpc/app.bsky.bookmark.listBookmarks"
        resp = requests.get(url, headers=headers, params={"limit": 10})
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
             print(resp.json())
        else:
             print(resp.text)
    except Exception as e:
        print(f"Req failed: {e}")
        
    print("\n--- Raw Request: app.bsky.feed.getTimeline (check viewer.bookmarked) ---")
    try:
        url = "https://bsky.social/xrpc/app.bsky.feed.getTimeline"
        resp = requests.get(url, headers=headers, params={"limit": 2})
        if resp.status_code == 200:
             data = resp.json()
             if 'feed' in data and len(data['feed']) > 0:
                 print("Checking first post viewer state:")
                 post = data['feed'][0]['post']
                 if 'viewer' in post:
                     print(post['viewer'])
                 else:
                     print("No viewer state in post.")
        else:
             print(resp.text)
    except Exception as e:
        print(f"Req failed: {e}")

if __name__ == "__main__":
    probe_raw()

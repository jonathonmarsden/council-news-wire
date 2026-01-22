import os
import sys
import getpass
from dotenv import load_dotenv
from atproto import Client

# Load .env
load_dotenv()

def probe_bookmarks(handle, password):
    print(f"Logging in as {handle}...")
    client = Client()
    try:
        client.login(handle, password)
        print("Login successful.")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    # URL Candidates
    # Based on user research: app.bsky.feed.getBookmarks
    endpoints = [
        "app.bsky.feed.getBookmarks",       
        "com.atproto.repo.listRecords",     # Fallback check (records)
        "app.bsky.actor.getPreferences",    # Check saved prefs
    ]

    print("\n--- Probing XRPC Endpoints ---")
    
    # Introspection: invalid method names might reveal available ones?
    # Or just try the high-level attributes
    
    # 1. Try high-level attribute access
    try:
        if hasattr(client.app.bsky.feed, 'get_bookmarks'):
             print("Found client.app.bsky.feed.get_bookmarks!")
             res = client.app.bsky.feed.get_bookmarks()
             print(res)
             return
        else:
             print("client.app.bsky.feed.get_bookmarks does not exist.")
    except Exception as e:
        print(f"Attr access error: {e}")

    # 2. Try low-level via _client.invoke or similar?
    # Inspect client object keys
    # print(dir(client))
    
    # 3. Known supported method for generic request?
    # Typically: client.call(method, params)
    # or client._sess.get(...)
    
    # Let's try raw Session request if exposed
    # client.request might have been the Request class, not method
    
    # Attempting raw XRPC request via requests using session headers
    import requests
    
    jwt = client._session.access_jwt
    headers = {"Authorization": f"Bearer {jwt}"}
    
    endpoints_to_try = [
        "https://bsky.social/xrpc/app.bsky.feed.getBookmarks",
        "https://bsky.social/xrpc/app.bsky.bookmark.getBookmarks"
    ]
    
    print("Trying raw HTTP requests...")
    for url in endpoints_to_try:
        print(f"GET {url}")
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            print("SUCCESS (Raw HTTP)!")
            print(r.json())
            return
        else:
            print(f"Failed: {r.status_code} {r.text}")
    

if __name__ == "__main__":
    if len(sys.argv) > 2:
        handle = sys.argv[1]
        password = sys.argv[2]
    else:
        # Check env vars first
        # Try generic, then Admin, then WA
        handle = os.environ.get('BSKY_HANDLE') or os.environ.get('BLUESKY_HANDLE_ADMIN') or os.environ.get('BLUESKY_HANDLE_WA')
        password = os.environ.get('BSKY_PASSWORD') or os.environ.get('BLUESKY_PASSWORD_ADMIN') or os.environ.get('BLUESKY_PASSWORD_WA')
        
        if not handle:
            print("Usage: python3 probe_bookmarks.py <handle> <password> or set BSKY_HANDLE/BSKY_PASSWORD")
            sys.exit(1)
    
    probe_bookmarks(handle, password)

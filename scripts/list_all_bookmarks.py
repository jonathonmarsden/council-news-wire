import os
import requests
import re
from dotenv import load_dotenv
from atproto import Client

load_dotenv()

BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE_ADMIN")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD_ADMIN")

def get_bookmarks(jwt, cursor=None):
    endpoint = "https://bsky.social/xrpc/app.bsky.bookmark.getBookmarks"
    headers = {"Authorization": f"Bearer {jwt}"}
    params = {}
    if cursor:
        params['cursor'] = cursor
    
    response = requests.get(endpoint, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def main():
    print(f"Authenticating as {BLUESKY_HANDLE}...")
    client = Client()
    client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
    jwt = client._session.access_jwt
    
    print("Fetching all bookmarks...")
    all_bookmarks = []
    cursor = None
    
    while True:
        data = get_bookmarks(jwt, cursor)
        if not data or 'bookmarks' not in data:
            break
            
        page = data['bookmarks']
        if not page:
            break
            
        all_bookmarks.extend(page)
        print(f"  Fetched {len(page)} items... (Total: {len(all_bookmarks)})")
        
        cursor = data.get('cursor')
        if not cursor:
            break
    
    print(f"\nDump of {len(all_bookmarks)} bookmarks:\n")
    print(f"{'IDX':<4} | {'HANDLE':<25} | {'FIRST LINE'}")
    print("-" * 80)
    
    for i, b in enumerate(all_bookmarks):
        item = b.get('item', {})
        record = item.get('record', {})
        text = record.get('text', '')
        author = item.get('author', {}).get('handle', 'unknown')
        lines = text.split('\n')
        first = lines[0].strip() if lines else "[EMPTY]"
        
        # Check malformed
        is_bad = False
        if re.match(r'^\d+$', first): is_bad = True # Starts with number
        if "Posted" in first and any(c.isdigit() for c in first): is_bad = True
        if "3673" in text: is_bad = True
        
        marker = " [BAD?]" if is_bad else ""
        print(f"{i+1:04d} | {author:<25} | {first[:50]}{marker}")

if __name__ == "__main__":
    main()

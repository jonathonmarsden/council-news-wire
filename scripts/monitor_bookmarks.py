import os
import requests
import json
from atproto import Client
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# Configuration
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE_ADMIN")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD_ADMIN")

if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
    print("Error: BLUESKY_HANDLE_ADMIN and BLUESKY_PASSWORD_ADMIN must be set in .env")
    exit(1)

def get_bookmarks(jwt, cursor=None):
    """Fetch bookmarks from the undocumented API."""
    endpoint = "https://bsky.social/xrpc/app.bsky.bookmark.getBookmarks"
    headers = {"Authorization": f"Bearer {jwt}"}
    params = {}
    if cursor:
        params['cursor'] = cursor
        
    try:
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching bookmarks: {e}")
        return None

def check_malformed(post_text):
    """
    Check for common malformation patterns.
    Returns a list of issues found.
    """
    issues = []
    
    # Check 1: Duplicated Date (e.g. "Posted 03 December 2025\n03 December 2025")
    lines = post_text.split('\n')
    for i in range(len(lines) - 1):
        line1 = lines[i].strip()
        line2 = lines[i+1].strip()
        if not line1 or not line2:
            continue
            
        date_pattern = r'\d{1,2}\s+[A-Za-z]+\s+\d{4}'
        if line1 == line2 or (("Posted" in line1) and (line1.replace("Posted ", "") == line2)):
             if re.search(date_pattern, line2):
                 issues.append("Duplicated Date Line")
                 break 
    
    return issues

def main():
    print(f"Authenticating as {BLUESKY_HANDLE}...")
    try:
        client = Client()
        profile = client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
        jwt = client._session.access_jwt
        print("Success.")
    except Exception as e:
        print(f"Auth failed: {e}")
        return

    print("Fetching ALL bookmarks (with pagination)...")
    all_bookmarks = []
    cursor = None
    
    while True:
        data = get_bookmarks(jwt, cursor)
        if not data or 'bookmarks' not in data:
            break
            
        page_bookmarks = data['bookmarks']
        all_bookmarks.extend(page_bookmarks)
        print(f"  Fetched {len(page_bookmarks)} items... (Total: {len(all_bookmarks)})")
        
        if len(page_bookmarks) == 0:
            break
            
        cursor = data.get('cursor')
        if not cursor:
            break
            
    print(f"\nScanning {len(all_bookmarks)} total bookmarks for issues and targets...\n")
    
    issues_found = 0
    
    print(f"{'ISSUE':<25} | {'HANDLE':<20} | {'TEXT SNIPPET'}")
    print("-" * 80)
    
    for b in all_bookmarks:
        item = b.get('item', {})
        record = item.get('record', {})
        text = record.get('text', '')
        author = item.get('author', {}).get('handle', 'unknown')
        uri = item.get('uri', '')
        
        # Debug specific target
        if "3mcygv7utar2b" in uri:
             print(f"\n[DEBUG TARGET FOUND]: {uri}")
             print(f"TEXT CONTENT:\n---\n{text}\n---\n")
             
        malformations = check_malformed(text)
        
        if malformations:
            issues_found += 1
            snippet = text.replace('\n', ' ')[:40] + "..."
            print(f"{malformations[0]:<25} | {author:<20} | {snippet}")
    
    print("-" * 80)
    if issues_found == 0:
        print("No malformed posts detected via STANDARD checks.")
    else:
        print(f"ALERT: Found {issues_found} potential malformed posts.")

if __name__ == "__main__":
    main()

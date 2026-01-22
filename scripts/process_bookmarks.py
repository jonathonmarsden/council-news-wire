import os
import requests
import re
import time
import json
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from atproto import Client

# Load environment variables
load_dotenv()

# Configuration
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE_ADMIN")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD_ADMIN")

if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
    print("Error: BLUESKY_HANDLE_ADMIN and BLUESKY_PASSWORD_ADMIN must be set in .env")
    exit(1)

def load_domain_map():
    """Load the domain-to-council map."""
    try:
        with open('scripts/council_domain_map.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading domain map: {e}")
        return {}

def get_council_name(url, text, domain_map, safelist):
    """
    Hybrid identification of Council Name.
    1. Check Domain Map (Safe).
    2. Check Text against Safelist (Fallback).
    """
    # 1. Domain Lookup
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        
        if domain in domain_map:
            return domain_map[domain], "domain_match"
    except:
        pass

    # 2. Text Safelist Scan
    # Look for exact matches of official names in the source text
    # We sort safelist by length (descending) to match "City of X" before "X" if needed, 
    # though usually names are distinct.
    found_names = []
    text_clean = text.replace('\n', ' ')
    
    for name in safelist:
        # Simple existence check
        if name in text_clean:
            found_names.append(name)
    
    # Only accept if exactly one council name is found to avoid ambiguity
    if len(found_names) == 1:
        return found_names[0], "text_safelist_match"
    
    # If we found multiple, it's ambiguous (e.g. "City of X met with Shire of Y")
    if len(found_names) > 1:
        # Heuristic: The one closer to the start is likely the author? 
        # Or just fail safely.
        return None, "ambiguous_match"
        
    return None, "unknown"

def get_all_bookmarks(jwt):
    """Fetch ALL bookmarks using pagination."""
    endpoint = "https://bsky.social/xrpc/app.bsky.bookmark.getBookmarks"
    headers = {"Authorization": f"Bearer {jwt}"}
    all_bookmarks = []
    cursor = None
    
    print("Fetching bookmarks...")
    while True:
        params = {}
        if cursor:
            params['cursor'] = cursor
            
        try:
            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'bookmarks' not in data:
                break
                
            batch = data['bookmarks']
            if not batch:
                break
                
            all_bookmarks.extend(batch)
            print(f"  Fetched {len(batch)} items... (Total: {len(all_bookmarks)})")
            
            cursor = data.get('cursor')
            if not cursor:
                break
                
        except Exception as e:
            print(f"Error fetching bookmarks: {e}")
            break
            
    return all_bookmarks

def fetch_real_title(url):
    """Fetch the page and extract the H1."""
    try:
        # User-Agent to avoid blocks
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Try H1
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
            if title:
                return title
        
        # Try og:title
        og_title = soup.find('meta', property='og:title')
        if og_title:
             return og_title.get('content', '').strip()
             
        # Try title tag
        if soup.title:
            return soup.title.get_text(strip=True).split('-')[0].strip() # detailed-ish
            
        return None
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def is_malformed(text):
    """Check if the post text indicates a malformed title."""
    lines = text.split('\n')
    if not lines:
        return False
    title_line = lines[0].strip()
    
    # Pattern 1: Starts with "Posted DD Month YYYY"
    if title_line.lower().startswith("posted ") and any(c.isdigit() for c in title_line):
        return True
        
    # Pattern 2: Starts with raw numbers (e.g. "3673")
    if re.match(r'^\d+$', title_line):
        return True
        
    # Pattern 3: Date-only start (e.g. "05 December 3673")
    if re.match(r'^\d{1,2} [A-Za-z]+ \d{4}', title_line):
        return True

    # Pattern 4: Future years (simple check for 3xxx)
    if " 3673" in text or " 3674" in text: # Known bad years
        return True
        
    # Pattern 6: Garbage Scrapes (Homepage/Footer text)
    bad_prefixes = [
        "© 20", "Image ", "Current page:", "Quick Links", "Shire Administration Office",
        "Welcome to the Shire", "Welcome to theShire", "Generic content", "Home"
    ]
    if any(title_line.startswith(p) for p in bad_prefixes):
        return True

    # Pattern 7: Date merged with title (e.g. "Fri 28 November 2025Early")
    if re.match(r'^[A-Za-z]{3} \d{1,2} [A-Za-z]+ \d{4}[A-Z]', title_line):
        return True

    return False

def get_bot_credentials(handle):
    """Determine state and credentials from handle."""
    match = re.search(r'roundupnewsbot([a-z]+)', handle)
    if not match:
        return None, None
        
    state_code = match.group(1).upper()
    env_handle = os.getenv(f"BLUESKY_HANDLE_{state_code}")
    env_pass = os.getenv(f"BLUESKY_PASSWORD_{state_code}")
    
    if env_handle and env_pass:
        return env_handle, env_pass
        
    return None, None

def main():
    # Load Maps
    print("Loading Council Data...")
    domain_map = load_domain_map()
    safelist = list(set(domain_map.values())) # Unique names
    # Sort safelist by length descending to match longeest possible name first
    safelist.sort(key=len, reverse=True)
    
    print(f"Loaded {len(domain_map)} domains and {len(safelist)} official names.")

    print(f"Authenticating as Admin ({BLUESKY_HANDLE})...")
    try:
        admin_client = Client()
        admin_client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
        jwt = admin_client._session.access_jwt
        print("Success.")
    except Exception as e:
        print(f"Auth failed: {e}")
        return

    print("Fetching bookmarks...")
    bookmarks = get_all_bookmarks(jwt)
    if not bookmarks:
        print("No bookmarks found.")
        return

    print(f"Found {len(bookmarks)} bookmarks. Grouping by bot...")
    
    # Group by author
    bot_tasks = {}
    for b in bookmarks:
        item = b.get('item', {})
        author = item.get('author', {}).get('handle')
        if author:
            if author not in bot_tasks:
                bot_tasks[author] = []
            bot_tasks[author].append(b)
            
    # Process per bot
    from core.poster import BlueSkyPoster
    
    for handle, items in bot_tasks.items():
        print(f"\nTraining Fixer on: {handle} ({len(items)} items)")
        
        bot_user, bot_pass = get_bot_credentials(handle)
        if not bot_user:
            print(f"  -> No credentials found for {handle}. Skipping.")
            continue
            
        try:
            bot_client = Client()
            bot_client.login(bot_user, bot_pass)
            poster = BlueSkyPoster(bot_user, bot_pass)
            print(f"  -> Logged in as {bot_user}")
        except Exception as e:
            print(f"  -> Login failed for {handle}: {e}")
            continue
            
        for b in items:
            item = b.get('item', {})
            uri = item.get('uri')
            record = item.get('record', {})
            text = record.get('text', '')
            
            # Extract Link first, we need it for ID
            facets = record.get('facets', [])
            link = None
            for f in facets:
                for feat in f.get('features', []):
                    if feat.get('$type') == 'app.bsky.richtext.facet#link':
                        link = feat.get('uri')
                        break
                if link: break
                
            if not link:
                print("    -> No link found. Skipping.")
                continue

            # Identify Council
            council_name, match_type = get_council_name(link, text, domain_map, safelist)

            if not council_name:
                print(f"    -> [SKIP] Unknown Council. URL: {link[:40]}...")
                continue

            print(f"  [PROCESSING]: {text[:40]}...")
            print(f"    -> Identified: {council_name} ({match_type})")
            
            real_title = fetch_real_title(link)
            if not real_title or is_malformed(real_title):
                print(f"    -> Bad scraped title: {real_title or 'None'}. Deleting garbage post.")
                try:
                    bot_client.delete_post(uri)
                    print("    -> Deleted garbage post.")
                    time.sleep(1)
                except Exception as e:
                    print(f"    -> Delete failed: {e}")
                continue
                
            print(f"    -> Retitle: '{real_title}'")

            # Additional check for generic titles
            BAD_TITLES = ["Home", "Quick Links", "Contact Us", "Privacy Policy", "Shire Administration Office", "News", "Latest News"]
            if any(t.lower() == real_title.lower() for t in BAD_TITLES):
                 print(f"    -> Title '{real_title}' is in blocklist. Deleting.")
                 try:
                    bot_client.delete_post(uri)
                 except: pass
                 continue
            
            # Helper to get tags/date from old text
            # Fix: re.findall strips the hash. We must add it back so poster can dedupe.
            raw_tags = re.findall(r'#(\w+)', text)
            tags = [f"#{t}" for t in raw_tags]
            
            # Post New FIRST
            new_uri = None
            try:
                # Use the clean PostWithFacets
                new_uri = poster.post_article(
                    council_name=council_name,
                    title=real_title,
                    url=link,
                    date=None,  # We don't guess dates anymore
                    hashtags=tags # Pass existing tags, poster will dedupe/sort
                )
                if new_uri:
                    print(f"    -> Reposted successfully. URI: {new_uri['uri'] if isinstance(new_uri, dict) else new_uri}")
                    time.sleep(2)
                else:
                    print("    -> Repost FAILED. Keeping old post.")
                    continue
            except Exception as e:
                print(f"    -> Repost exception: {e}")
                continue

            # Delete Old ONLY if new one succeeded
            try:
                bot_client.delete_post(uri)
                print("    -> Deleted old post.")
            except Exception as e:
                 print(f"    -> Error deleting old post: {e}")

if __name__ == "__main__":
    main()


import json
import os
import requests
import concurrent.futures
from urllib.parse import urlparse, urljoin
import xml.etree.ElementTree as ET

# Configuration
TIMEOUT = 10
MAX_WORKERS = 20
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

COMMON_PATHS = [
    "/feed",
    "/feed/",
    "/rss",
    "/rss/",
    "/news/rss",
    "/news/feed",
    "/media-releases/rss",
    "/media-releases/feed",
    "/latest-news/rss",
    "/council-news/rss",
    "/rss.xml",
    "/atom.xml"
]

def load_zero_yield_councils():
    """Parses ZERO_YIELD_COUNCILS.md to get a list of failing councils."""
    councils = []
    try:
        with open("ZERO_YIELD_COUNCILS.md", "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.strip().startswith("|") and not line.strip().startswith("| State"):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 5:
                        state = parts[1]
                        council_id = parts[2]
                        name = parts[3]
                        url = parts[4]
                        councils.append({
                            "state": state,
                            "id": council_id,
                            "name": name,
                            "url": url
                        })
    except FileNotFoundError:
        print("ZERO_YIELD_COUNCILS.md not found.")
    return councils

def check_url(url):
    """Checks if a URL returns a valid RSS/Atom feed."""
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "").lower()
            content = response.content[:1000].lower() # Check first 1000 bytes
            
            is_xml = "xml" in content_type or b"<?xml" in content
            is_rss = b"<rss" in content or b"<feed" in content or b"<channel" in content
            
            if is_xml and is_rss:
                return url
    except Exception:
        pass
    return None

def probe_council(council):
    """Probes a single council for RSS feeds."""
    base_url = council["url"]
    parsed = urlparse(base_url)
    root_url = f"{parsed.scheme}://{parsed.netloc}"
    
    # Generate candidate URLs
    candidates = []
    
    # 1. Common paths on root
    for path in COMMON_PATHS:
        candidates.append(urljoin(root_url, path))
        
    # 2. Common paths relative to the news URL (if it's a subfolder)
    # e.g. if news_url is .../council/news, try .../council/news/rss
    if parsed.path and parsed.path != "/":
        path_stripped = parsed.path.rstrip("/")
        for path in COMMON_PATHS:
            candidates.append(urljoin(root_url, path_stripped + path))

    # Deduplicate
    candidates = list(set(candidates))
    
    found_feeds = []
    for url in candidates:
        if check_url(url):
            found_feeds.append(url)
            # If we find one, we can probably stop, but finding multiple might be useful.
            # For now, let's just return the first valid one to save time.
            return council, url
            
    return council, None

def main():
    councils = load_zero_yield_councils()
    print(f"Loaded {len(councils)} failing councils.")
    print(f"Probing for RSS feeds with {MAX_WORKERS} workers...")
    
    found_count = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_council = {executor.submit(probe_council, council): council for council in councils}
        
        for future in concurrent.futures.as_completed(future_to_council):
            council, feed_url = future.result()
            if feed_url:
                found_count += 1
                print(f"[FOUND] {council['state']}/{council['id']}: {feed_url}")
                
                # Log to file immediately
                with open("rss_discoveries.txt", "a") as f:
                    f.write(f"{council['state']}|{council['id']}|{feed_url}\n")
    
    print(f"\nScan complete. Found {found_count} potential RSS feeds.")

if __name__ == "__main__":
    main()

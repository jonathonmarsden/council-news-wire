import json
import sys
import argparse
from pathlib import Path
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

def load_council(council_id, state_code=None):
    states_dir = PROJECT_ROOT / 'states'
    for state_dir in states_dir.iterdir():
        if not state_dir.is_dir() or state_dir.name.startswith('_'):
            continue
        if state_code and state_dir.name != state_code:
            continue
            
        councils_file = state_dir / 'councils.json'
        if councils_file.exists():
            with open(councils_file, 'r') as f:
                data = json.load(f)
                for council in data.get('councils', []):
                    if council['id'] == council_id:
                        return council, state_dir.name
    return None, None

def check_council(council_id):
    council, state = load_council(council_id)
    if not council:
        print(f"Council {council_id} not found.")
        return

    print(f"Checking {council['name']} ({state})")
    url = council.get('news_url')
    print(f"URL: {url}")
    
    use_curl = council.get('use_curl', False) or council.get('scraper') == 'curl_scraper'
    impersonate = council.get('impersonate', 'chrome110')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
    }

    try:
        if use_curl:
            print(f"Using curl_cffi with impersonate={impersonate}")
            r = curl_requests.get(url, impersonate=impersonate, headers=headers, timeout=20)
        else:
            print("Using standard requests")
            import requests
            r = requests.get(url, headers=headers, timeout=20, verify=False)
            
        print(f"Status: {r.status_code}")
        print(f"Content-Length: {len(r.text)}")
        
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.title.string.strip() if soup.title else "No Title"
        print(f"Page Title: {title}")
        
        item_selector = council.get('item_selector')
        if item_selector:
            items = soup.select(item_selector)
            print(f"Found {len(items)} items with selector '{item_selector}'")
            if len(items) > 0:
                first = items[0]
                print(f"First item HTML snippet: {str(first)[:200]}")
                
                title_sel = council.get('title_selector')
                if title_sel:
                    t = first.select_one(title_sel)
                    print(f"  Title extract: {t.get_text(strip=True) if t else 'NOT FOUND'}")
                    
                link_sel = council.get('link_selector')
                if link_sel:
                    l = first.select_one(link_sel) if link_sel != 'self' else first
                    # Handle a.select_one('a') if link_selector is 'a' inside item
                    if not l and first.name == 'a': l = first
                    
                    print(f"  Link extract: {l.get('href') if l else 'NOT FOUND'}")
        else:
            print("No item_selector defined.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/check_site.py <council_id>")
    else:
        check_council(sys.argv[1])

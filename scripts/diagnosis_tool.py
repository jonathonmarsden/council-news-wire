import json
import sys
import time
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from core.scrapers import ScraperFactory

# Common blocking signatures
BLOCK_SIGNATURES = [
    "Just a moment...",
    "Attention Required! | Cloudflare",
    "Incapsula",
    "Request unsuccessful. Incapsula incident ID"
]

def load_all_councils():
    all_councils = []
    states_dir = PROJECT_ROOT / 'states'
    for state_dir in states_dir.iterdir():
        if not state_dir.is_dir() or state_dir.name.startswith('_'):
            continue
        councils_file = state_dir / 'councils.json'
        if councils_file.exists():
            try:
                with open(councils_file, 'r') as f:
                    data = json.load(f)
                    for c in data.get('councils', []):
                        c['state'] = state_dir.name
                        all_councils.append(c)
            except Exception as e:
                print(f"Error loading {state_dir.name}: {e}")
    return all_councils

def check_url_curl(url):
    try:
        resp = curl_requests.get(url, impersonate="chrome110", timeout=30)
        return resp.status_code, resp.text, None
    except Exception as e:
        return 0, "", str(e)

def check_url_requests(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=30)
        return resp.status_code, resp.text, None
    except Exception as e:
        return 0, "", str(e)

def diagnose_council(council):
    print(f"Diagnosing {council['name']} ({council['state']})")
    
    url = council.get('news_url') or council.get('rss_url')
    if not url:
        return "NO_URL"

    # 1. Try Standard Requests
    r_status, r_text, r_err = check_url_requests(url)
    
    # 2. Try Curl
    c_status, c_text, c_err = check_url_curl(url)
    
    diagnosis = {
        "council": council['name'],
        "state": council['state'],
        "current_method": "curl" if council.get("use_curl") else "requests",
        "requests_status": r_status,
        "curl_status": c_status,
        "likely_waf": False,
        "selector_found": False,
        "recommendation": "Manual Review"
    }

    # Check WAF
    for sig in BLOCK_SIGNATURES:
        if sig in r_text:
            diagnosis["likely_waf"] = True
            diagnosis["waf_source"] = "requests_body"
        if sig in c_text:
            diagnosis["likely_waf"] = True
            diagnosis["waf_source"] = "curl_body"
            
    if r_status in [403, 406] or c_status in [403, 406]:
        diagnosis["likely_waf"] = True

    # Check Selectors (using the best content)
    html = c_text if c_status == 200 else r_text
    if html:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Get configured selector
        selectors = council.get('selectors', {})
        item_selector = selectors.get('container') or council.get('item_selector')
        
        if item_selector:
            found = soup.select(item_selector)
            if found:
                diagnosis["selector_found"] = True
                diagnosis["item_count"] = len(found)
            else:
                diagnosis["selector_found"] = False
                
    # Recommendations
    if diagnosis["likely_waf"] and council.get("use_curl"):
        diagnosis["recommendation"] = "HARD_BLOCK: Even Curl is blocked."
    elif diagnosis["likely_waf"] and not council.get("use_curl"):
        diagnosis["recommendation"] = "ENABLE_CURL: WAF detected."
    elif diagnosis["requests_status"] != 200 and diagnosis["curl_status"] == 200:
        diagnosis["recommendation"] = "ENABLE_CURL: Requests failed, Curl succeeded."
    elif diagnosis["item_count"] if "item_count" in diagnosis else 0 == 0:
        diagnosis["recommendation"] = "FIX_SELECTOR: Page loads but 0 items found."
        
    return diagnosis

def main():
    target_names = [
        # Paste list of target names here or load from file
        "Georges River Council", "Lake Macquarie, City of", "Northern Beaches Council",
        "Tweed Shire", "Bellingen Shire", "Bogan Shire", "Clarence Valley Council",
        "Hay Shire", "Lockhart Shire", "Inverell Shire", "Moree Plains Shire",
        "Murray River Council", "Murrumbidgee Council", "Narrandera Shire",
        "Shellharbour, City of", "Upper Lachlan Shire", "Snowy Valleys Council", 
        "Uralla Shire", "Lithgow, City of", "Wollondilly Shire"
    ]
    
    # Or just use the passed args
    if len(sys.argv) > 1:
        target_names = sys.argv[1:]

    all_councils = load_all_councils()
    targets = [c for c in all_councils if c['name'] in target_names]
    
    if not targets:
        print("No targets found.")
        return

    print(f"Diagnosing {len(targets)} councils...")
    results = []
    
    for c in targets:
        res = diagnose_council(c)
        results.append(res)
        print(f"-> {res['recommendation']} (WAF: {res['likely_waf']}, ITEMS: {res.get('item_count', 0)})")
        time.sleep(1) # Be polite

    # Summary
    print("\nSummary Recommendations:")
    for r in results:
        print(f"{r['council']}: {r['recommendation']}")

if __name__ == "__main__":
    main()

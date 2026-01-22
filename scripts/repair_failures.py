import json
import sys
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# List of failing councils from the Health Check
TARGETS = [
    # NT
    "Barkly Regional Council", "Coomalie Community Government Council", "East Arnhem Regional Council",
    "MacDonnell Regional Council", "Wagait Shire", "Groote Archipelago Regional Council",
    # SA
    "City of Adelaide", "Naracoorte Lucindale Council", "Renmark Paringa Council",
    "City of Port Augusta", "City of Salisbury", "City of Unley", "City of West Torrens",
    # QLD
    "Blackall-Tambo Council", "Bundaberg Council", "Cherbourg Aboriginal Shire",
    "Shire of Etheridge", "Lockyer Valley Council", "Shire of Richmond", "Shire of Quilpie",
    "Aboriginal Shire of Wujal Wujal",
    # NSW
    "Georges River Council", "Lake Macquarie, City of", "Northern Beaches Council",
    "Tweed Shire", "Bellingen Shire", "Bogan Shire", "Clarence Valley Council",
    "Hay Shire", "Lockhart Shire", "Inverell Shire", "Moree Plains Shire",
    "Murray River Council", "Murrumbidgee Council", "Narrandera Shire",
    "Shellharbour, City of", "Upper Lachlan Shire", "Snowy Valleys Council", 
    "Uralla Shire", "Lithgow, City of", "Wollondilly Shire",
    # WA
    "City of Armadale", "Shire of Augusta Margaret River", "Shire of Broomehill-Tambellup",
    "Town of Cottesloe", "Shire of Cocos (Keeling) Islands", "Shire of Dandaragan",
    "Shire of Dumbleyung", "Shire of Dardanup", "Shire of Esperance",
    "Town of East Fremantle", "Shire of Halls Creek", "Shire of Goomalling",
    "Shire of Harvey", "Shire of Kojonup", "City of Kwinana", "Shire of Manjimup",
    "City of Mandurah", "Shire of Meekatharra", "Shire of Merredin", "Shire of Moora",
    "Shire of Nannup", "Shire of Narembeen", "Shire of Nungarin", "Shire of Northam",
    "Shire of Mount Magnet", "Shire of Peppermint Grove", "Shire of Sandstone",
    "City of Swan", "Shire of Tammin", "City of Subiaco", "Shire of Trayning",
    "City of Vincent", "Shire of Quairading" 
]

def load_all_councils():
    councils_map = {}
    states_dir = PROJECT_ROOT / 'states'
    for state_dir in states_dir.iterdir():
        if not state_dir.is_dir() or state_dir.name.startswith('_'):
            continue
        councils_file = state_dir / 'councils.json'
        if councils_file.exists():
            with open(councils_file, 'r') as f:
                data = json.load(f)
                for c in data.get('councils', []):
                    c['state'] = state_dir.name
                    councils_map[c['name']] = c
    return councils_map

def find_rss_in_html(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    
    # 1. Standard discovery
    for link in soup.find_all('link', type='application/rss+xml'):
        href = link.get('href')
        if href:
            links.append(href)
            
    for link in soup.find_all('link', type='application/atom+xml'):
        href = link.get('href')
        if href:
            links.append(href)
            
    # 2. Heuristic search in a tags
    for a in soup.find_all('a'):
        href = a.get('href')
        if href and ('rss' in href.lower() or 'feed' in href.lower()) and ('.xml' in href or 'format=feed' in href):
            links.append(href)
            
    # Normalize
    full_links = []
    for l in links:
        if l.startswith('/'):
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            l = f"{parsed.scheme}://{parsed.netloc}{l}"
        if l not in full_links:
            full_links.append(l)
            
    return full_links

def main():
    map_data = load_all_councils()
    
    found_rss = {}
    
    print(f"Checking {len(TARGETS)} councils for RSS availability...")
    
    for name in TARGETS:
        if name not in map_data:
            print(f"SKIP: {name} not found in configs?")
            continue
            
        council = map_data[name]
        url = council.get('news_url')
        if not url:
            continue
            
        # Already RSS?
        if council.get('rss_url'):
            print(f"SKIP: {name} is already RSS")
            continue
            
        print(f"Checking {name} ({url})...")
        
        try:
            # Use curl to bypass WAF if present
            resp = curl_requests.get(url, impersonate="chrome110", timeout=15)
            if resp.status_code == 200:
                rss_links = find_rss_in_html(resp.text, url)
                if rss_links:
                    print(f"  ✅ FOUND RSS for {name}: {rss_links[0]}")
                    found_rss[name] = rss_links[0]
                else:
                    print(f"  ❌ No RSS found in metadata")
            else:
                print(f"  ❌ Failed to fetch: {resp.status_code}")
                
        except Exception as e:
            print(f"  ❌ Exception: {e}")

    # Report
    print("\n=== RSS DISCOVERY REPORT ===")
    for name, feed in found_rss.items():
        print(f'"{name}": "{feed}"')
        
    # TODO: Could auto-apply these
    
if __name__ == "__main__":
    main()

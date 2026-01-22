import json
import sys
import requests
from pathlib import Path
from curl_cffi import requests as curl_requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

TARGETS = [
    # NSW
    "Hay Shire", "Lockhart Shire", "Moree Plains Shire",
    "Shellharbour, City of", "Wollondilly Shire",
    "Lake Macquarie, City of", "Tweed Shire", "Bellingen Shire", "Clarence Valley Council",
    "Murray River Council", "Murrumbidgee Council", "Narrandera Shire", "Snowy Valleys Council",
    "Uralla Shire",
    # WA (The 33 failures)
     "City of Armadale", "Shire of Augusta Margaret River", "Town of Cottesloe",
     "City of Mandurah", "City of Kwinana", "Shire of Harvey", "City of Swan"
]

def load_council_url(name):
    states_dir = PROJECT_ROOT / 'states'
    for state_dir in states_dir.iterdir():
        if not state_dir.is_dir() or state_dir.name.startswith('_'): continue
        config_path = state_dir / 'councils.json'
        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)
                for c in data['councils']:
                    if c['name'] == name:
                        return c.get('news_url'), state_dir.name
    return None, None

def detect_vendor(html):
    if "OpenCities" in html or "OC_Content" in html or "oc-widget" in html:
        return "OpenCities"
    if "Catalyst" in html or "catalyst-plugin" in html or "ctl00_Content" in html:
        # Check for typical Catalyst ASP.NET structure often viewed in WA
        if "MyCouncil" in html: return "Catalyst"
    if "wp-content" in html:
        return "WordPress"
    if "Squiz" in html or "squiz" in html.lower():
        return "Squiz"
    if "Shire of" in html and "wa.gov.au" in html:
        # Generic WA heuristic
        pass
    return "Unknown"

def main():
    print(f"Scanning {len(TARGETS)} councils for vendor signatures...")
    
    for name in TARGETS:
        url, state = load_council_url(name)
        if not url:
            print(f"SKIP: {name}")
            continue
            
        try:
            resp = curl_requests.get(url, impersonate="chrome110", timeout=15)
            vendor = detect_vendor(resp.text)
            print(f"{name} ({state}): {vendor}")
        except Exception as e:
            print(f"{name} ({state}): Error {str(e)[:50]}")

if __name__ == "__main__":
    main()

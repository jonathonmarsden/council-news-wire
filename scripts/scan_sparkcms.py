import json
import asyncio
from curl_cffi import requests
from bs4 import BeautifulSoup
import os

# Configuration
STATE_FILE = "states/wa/councils.json"
TARGET_SELECTOR = ".module-list .row"
IMPERSONATE = "chrome120"

async def check_council(council):
    url = council.get("news_url")
    if not url:
        return None
        
    print(f"Checking {council['id']} ({url})...")
    
    try:
        # Run in executor to avoid blocking
        response = await asyncio.to_thread(
            requests.get, 
            url, 
            impersonate=IMPERSONATE,
            timeout=15
        )
        
        if response.status_code != 200:
            print(f"❌ {council['id']}: Status {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check for the specific SparkCMS structure
        matches = soup.select(TARGET_SELECTOR)
        
        if matches:
            print(f"✅ MATCH FOUND: {council['id']} has {len(matches)} items matching '{TARGET_SELECTOR}'")
            return {
                "id": council['id'],
                "url": url,
                "matches": len(matches),
                "current_scraper": council.get("scraper"),
                "current_selector": council.get("item_selector")
            }
        else:
            # Check for partial matches or indicators
            if "module-list" in response.text:
                print(f"⚠️ PARTIAL MATCH: {council['id']} has 'module-list' but selector failed.")
            return None
            
    except Exception as e:
        print(f"❌ ERROR {council['id']}: {str(e)}")
        return None

async def main():
    if not os.path.exists(STATE_FILE):
        print(f"File not found: {STATE_FILE}")
        return

    with open(STATE_FILE, 'r') as f:
        data = json.load(f)
        
    tasks = []
    councils = data.get("councils", [])
    
    # Filter for councils that might be candidates (ignoring known good ones if needed, but let's scan all non-Catalyst/non-OpenCities for now)
    # Actually, let's scan everything just to be sure.
    
    print(f"Scanning {len(councils)} WA councils for SparkCMS signature '{TARGET_SELECTOR}'...")
    
    results = []
    for council in councils:
        # Optional: Skip known good ones to save time? 
        # But 'esperance' is a match, so we want to verify the scanner works by finding it.
        result = await check_council(council)
        if result:
            results.append(result)
            
    print("\n\n=== SUMMARY OF MATCHES ===")
    for r in results:
        print(f"{r['id']}: {r['matches']} items. (Current Scraper: {r['current_scraper']})")
        
    # Suggest specific updates
    print("\n=== SUGGESTED CONFIG UPDATES ===")
    for r in results:
        if r['current_selector'] != TARGET_SELECTOR:
             print(f"""
        {{
            "id": "{r['id']}",
            "scraper": "curl_scraper",
            "item_selector": "{TARGET_SELECTOR}",
            "title_selector": "span.h4",
            "date_selector": "span.h5",
            "link_selector": "a.btn",
            "enabled": true,
            "use_curl": true
        }},""")

if __name__ == "__main__":
    asyncio.run(main())

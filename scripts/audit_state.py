
import json
import os
import sys
import argparse
import concurrent.futures
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from core.scrapers.factory import ScraperFactory

def check_council(council):
    """
    Runs the scraper for a single council and returns the result.
    """
    result = {
        "id": council.get("id"),
        "name": council.get("name"),
        "url": council.get("news_url"),
        "scraper": council.get("scraper", "default"),
        "status": "unknown",
        "count": 0,
        "error": None,
        "sample": None
    }
    
    if not council.get("enabled", True):
        result["status"] = "disabled"
        return result

    try:
        scraper = ScraperFactory.create_scraper(council)
        # We assume scrape() is synchronous. If ScraperFactory returns async scrapers, we need to adjust.
        # Based on previous context, they seem synchronous (playwright uses sync_api).
        articles = scraper.scrape()
        
        result["count"] = len(articles)
        if result["count"] > 0:
            result["status"] = "ok"
            result["sample"] = f"{articles[0].title} ({articles[0].date})"
        else:
            result["status"] = "zombie" # 200 OK but 0 items
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        
    return result

def audit_state(state):
    config_path = f"states/{state}/councils.json"
    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        return

    print(f"Loading config from {config_path}...")
    with open(config_path, 'r') as f:
        data = json.load(f)
        
    councils = data.get("councils", [])
    print(f"Found {len(councils)} councils for {state.upper()}. Starting audit...")
    
    results = []
    
    # Run sequentially for now to avoid resource contention (especially with browsers)
    # or use a small pool. Browsers are heavy.
    # Let's verify existing zombies first - maybe we don't assume any are working.
    
    zombies = []
    errors = []
    
    for council in councils:
        print(f"Checking {council.get('name')} ({council.get('id')})...")
        res = check_council(council)
        results.append(res)
        
        if res["status"] == "zombie":
            print(f"  [!] ZOMBIE DETECTED: 0 articles found.")
            zombies.append(res)
        elif res["status"] == "error":
            print(f"  [X] ERROR: {res['error']}")
            errors.append(res)
        elif res["status"] == "ok":
            print(f"  [+] OK: {res['count']} articles. Sample: {res['sample']}")
        elif res["status"] == "disabled":
            print(f"  [-] Disabled.")
            
    print("\n" + "="*60)
    print(f"AUDIT COMPLETE FOR {state.upper()}")
    print("="*60)
    print(f"Total: {len(results)}")
    print(f"OK: {len([r for r in results if r['status'] == 'ok'])}")
    print(f"Zombies (0 items): {len(zombies)}")
    print(f"Errors: {len(errors)}")
    print("="*60)
    
    if zombies:
        print("\nZOMBIES LIST:")
        for z in zombies:
            print(f"- {z['name']} ({z['id']}): {z['url']} [{z['scraper']}]")
            
    if errors:
        print("\nERRORS LIST:")
        for e in errors:
            print(f"- {e['name']} ({e['id']}): {e['error']}")

    # Save report
    report_file = f"audit_report_{state}_{datetime.now().strftime('%Y%m%d')}.json"
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nReport saved to {report_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Audit councils for a specific state.')
    parser.add_argument('state', help='State code (e.g., nsw, vic, wa)')
    args = parser.parse_args()
    
    audit_state(args.state.lower())

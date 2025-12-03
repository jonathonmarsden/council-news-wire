#!/usr/bin/env python3
"""
WAF Verification Tool

Verifies that the councils we switched to `use_curl: true` are actually working.
Runs a scrape for each and checks if we get a 200 OK and some content.
"""

import json
import os
import sys
import concurrent.futures
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from core.config import CONFIG_PATHS
from core.scrapers import ScraperFactory

def load_curl_councils():
    councils = []
    for state, config_path in CONFIG_PATHS.items():
        if config_path.exists():
            with open(config_path, 'r') as f:
                try:
                    data = json.load(f)
                    for c in data.get('councils', []):
                        if c.get('use_curl', False) and c.get('enabled', True):
                            c['state'] = state
                            councils.append(c)
                except json.JSONDecodeError:
                    pass
    return councils

def verify_council(council):
    try:
        # Create scraper instance
        scraper = ScraperFactory.create_scraper(council)
        
        # We just want to fetch the page, not parse everything fully if we don't have to
        # But calling scrape() is the easiest way to test the full pipeline
        # However, scrape() might be slow. Let's just try fetch_page first.
        
        content = scraper.fetch_page(council['news_url'])
        
        if content and len(content) > 1000:
            return {'council': council, 'status': 'SUCCESS', 'length': len(content)}
        else:
            return {'council': council, 'status': 'EMPTY_CONTENT', 'length': len(content) if content else 0}
            
    except Exception as e:
        return {'council': council, 'status': 'ERROR', 'error': str(e)}

def main():
    print("🔍 Verifying WAF Fixes (curl_cffi)...")
    curl_councils = load_curl_councils()
    print(f"Found {len(curl_councils)} councils using curl.")
    
    results = []
    
    # Limit concurrency to avoid overwhelming the machine or getting banned
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_council = {executor.submit(verify_council, c): c for c in curl_councils}
        
        completed = 0
        for future in concurrent.futures.as_completed(future_to_council):
            completed += 1
            if completed % 10 == 0:
                print(f"Progress: {completed}/{len(curl_councils)}")
            results.append(future.result())
            
    # Analyze Results
    success = [r for r in results if r['status'] == 'SUCCESS']
    failed = [r for r in results if r['status'] != 'SUCCESS']
    
    print(f"\n📊 Verification Complete")
    print(f"✅ Success: {len(success)}")
    print(f"❌ Failed: {len(failed)}")
    
    if failed:
        print("\n❌ Failures:")
        for f in failed:
            c = f['council']
            print(f"  - {c['name']} ({c['state']}): {f['status']} - {f.get('error', '')}")

if __name__ == "__main__":
    main()

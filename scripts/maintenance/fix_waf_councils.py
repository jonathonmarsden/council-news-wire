#!/usr/bin/env python3
"""
WAF Fixer Script

Iterates through councils that are returning 403 Forbidden (WAF Blocked).
Enables `use_curl: true` in their configuration to bypass Cloudflare/Incapsula.
"""

import json
import os
import sys
import requests
import concurrent.futures
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from core.config import CONFIG_PATHS

# Common headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

def load_all_councils():
    councils = []
    for state, config_path in CONFIG_PATHS.items():
        if config_path.exists():
            with open(config_path, 'r') as f:
                try:
                    data = json.load(f)
                    for c in data.get('councils', []):
                        c['state'] = state
                        c['config_path'] = config_path
                        councils.append(c)
                except json.JSONDecodeError:
                    pass
    return councils

def check_and_fix(council):
    url = council.get('news_url')
    if not url:
        return None

    # Skip if already using curl
    if council.get('use_curl'):
        return None

    try:
        # Check if it's blocked
        response = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        
        if response.status_code == 403:
            print(f"🔒 Detected WAF Block (403) for {council['name']} ({council['state']})")
            return council
            
    except Exception:
        pass
        
    return None

def apply_fix(councils_to_fix):
    # Group by config file to minimize writes
    by_config = {}
    for c in councils_to_fix:
        path = c['config_path']
        if path not in by_config:
            by_config[path] = []
        by_config[path].append(c['id'])
        
    for config_path, council_ids in by_config.items():
        with open(config_path, 'r') as f:
            data = json.load(f)
            
        updated = False
        for c in data['councils']:
            if c['id'] in council_ids:
                c['use_curl'] = True
                # Also enable rotating proxy for good measure on stubborn ones?
                # Let's stick to just curl for now.
                updated = True
                print(f"  ✅ Enabled use_curl for {c['name']}")
                
        if updated:
            with open(config_path, 'w') as f:
                json.dump(data, f, indent=4)

def main():
    print("🔍 Scanning for WAF blocked councils (403)...")
    all_councils = load_all_councils()
    
    # Filter to only those not already using curl
    candidates = [c for c in all_councils if not c.get('use_curl')]
    
    blocked_councils = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_council = {executor.submit(check_and_fix, c): c for c in candidates}
        
        completed = 0
        for future in concurrent.futures.as_completed(future_to_council):
            completed += 1
            if completed % 20 == 0:
                print(f"Progress: {completed}/{len(candidates)}")
            
            result = future.result()
            if result:
                blocked_councils.append(result)
                
    print(f"\nFound {len(blocked_councils)} councils needing WAF bypass.")
    
    if blocked_councils:
        print("Applying fixes...")
        apply_fix(blocked_councils)
        print("Done.")
    else:
        print("No new WAF blocks found.")

if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    main()

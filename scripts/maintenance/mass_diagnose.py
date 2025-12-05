
import json
import os
import sys
import concurrent.futures
import time
from datetime import datetime
import glob

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scrapers import ScraperFactory

def load_zero_yield_councils():
    """Parse the ZERO_YIELD_COUNCILS.md file to get the list of target councils."""
    targets = []
    try:
        with open('ZERO_YIELD_COUNCILS.md', 'r') as f:
            lines = f.readlines()
            
        # Skip header lines (find the table start)
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('| State | ID |'):
                start_idx = i + 2 # Skip header and separator
                break
        
        for line in lines[start_idx:]:
            if not line.strip() or not line.startswith('|'):
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 4:
                # | State | ID | Name | URL |
                # parts[0] is empty string because line starts with |
                state = parts[1]
                c_id = parts[2]
                targets.append((state, c_id))
    except FileNotFoundError:
        print("ZERO_YIELD_COUNCILS.md not found.")
        return []
    return targets

def get_council_config(state, c_id):
    path = f"states/{state}/councils.json"
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            for c in data.get('councils', []):
                if c['id'] == c_id:
                    return c
    except Exception:
        pass
    return None

def diagnose_council(council):
    """Run a single scraper and return the result category."""
    start_time = time.time()
    try:
        scraper = ScraperFactory.create_scraper(council)
        if not scraper:
            return "CONFIG_ERROR", "Could not create scraper"
            
        # Attempt scrape
        articles = scraper.scrape()
        duration = time.time() - start_time
        
        if len(articles) > 0:
            return "SUCCESS", f"Found {len(articles)} articles"
        else:
            return "EMPTY", "Scraper ran but found 0 articles"
            
    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        
        # Categorize Error
        if "403" in error_msg or "Forbidden" in error_msg:
            return "WAF_BLOCK", "403 Forbidden"
        elif "404" in error_msg:
            return "BROKEN_LINK", "404 Not Found"
        elif "SSLError" in error_msg or "CertificateError" in error_msg:
            return "SSL_ERROR", "SSL Certificate Issue"
        elif "ConnectionError" in error_msg or "ConnectTimeout" in error_msg:
            return "CONNECTION_ERROR", "Connection Failed"
        elif "'NoneType' object is not iterable" in error_msg:
            return "PARSE_ERROR", "Selector returned None"
        else:
            return "UNKNOWN_ERROR", error_msg

def main():
    print("Loading Zero Yield Councils...")
    targets = load_zero_yield_councils()
    print(f"Found {len(targets)} councils to diagnose.")
    
    results = {
        "SUCCESS": [],
        "EMPTY": [],
        "WAF_BLOCK": [],
        "BROKEN_LINK": [],
        "SSL_ERROR": [],
        "CONNECTION_ERROR": [],
        "PARSE_ERROR": [],
        "CONFIG_ERROR": [],
        "UNKNOWN_ERROR": []
    }
    
    # Limit to 20 for a quick sample run, or run all?
    # Let's run a sample of 20 first to gauge the landscape
    sample_targets = targets[:20] 
    print(f"Running diagnosis on first {len(sample_targets)} targets...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_council = {}
        for state, c_id in sample_targets:
            config = get_council_config(state, c_id)
            if config:
                future = executor.submit(diagnose_council, config)
                future_to_council[future] = (state, c_id)
            else:
                print(f"Warning: Config not found for {state}/{c_id}")
                
        for future in concurrent.futures.as_completed(future_to_council):
            state, c_id = future_to_council[future]
            try:
                category, message = future.result()
                results[category].append(f"{state}/{c_id}: {message}")
                print(f"[{category}] {state}/{c_id}: {message}")
            except Exception as e:
                print(f"CRITICAL ERROR {state}/{c_id}: {e}")

    print("\n=== DIAGNOSIS SUMMARY ===")
    for category, items in results.items():
        if items:
            print(f"\n{category}: {len(items)}")
            for item in items:
                print(f"  - {item}")

if __name__ == "__main__":
    main()

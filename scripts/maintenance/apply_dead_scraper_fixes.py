
import json
import os
import re
import difflib

REPORT_FILE = 'DEAD_SCRAPERS_REPORT_2026.md'

def get_ssr_list():
    """Parses the 'Auto-Fixed (Switched to RSS)' table from the report."""
    fixes = []
    with open(REPORT_FILE, 'r') as f:
        lines = f.readlines()
    
    in_table = False
    for line in lines:
        if "## 🛠️ Auto-Fixed (Switched to RSS)" in line:
            in_table = True
            continue
        if "## ⚠️ WAF Blocked" in line:
            break
        
        if in_table and line.strip().startswith('|'):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 4 and parts[1] != 'State' and '---' not in parts[1]:
                state = parts[1].lower()
                council_name = parts[2]
                rss_url = parts[3]
                fixes.append({
                    'state': state,
                    'name': council_name,
                    'rss_url': rss_url
                })
    return fixes

def normalize_name(name):
    """Removes common suffixes and normalizes for comparison."""
    # Remove common words
    words = ['council', 'shire', 'city', 'regional', 'municipal', 'district', 'aboriginal', 'of', 'the', '-', '–']
    name = name.lower()
    for word in words:
        name = name.replace(word, '')
    # Remove extra spaces
    return re.sub(r'\s+', ' ', name).strip()

def apply_fixes(fixes):
    # Group by state
    state_fixes = {}
    for fix in fixes:
        if fix['state'] not in state_fixes:
            state_fixes[fix['state']] = []
        state_fixes[fix['state']].append(fix)
    
    for state, items in state_fixes.items():
        json_path = f"states/{state}/councils.json"
        
        if not os.path.exists(json_path):
            print(f"Checking mapped paths for {state}")
            pass
            
        print(f"Processing {state} ({len(items)} fixes)...")
        
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"File not found: {json_path}")
            continue
            
        councils = data.get('councils', [])
        modified_count = 0
        
        def update_council(council, url):
            council['news_url'] = url
            council['scraper'] = 'rss_scraper'
            fields_to_remove = ['item_selector', 'title_selector', 'link_selector', 'date_selector', 'date_format', 'verify_cert']
            for field in fields_to_remove:
                if field in council:
                    del council[field]
        
        for item in items:
            target_name = item['name']
            new_url = item['rss_url']
            
            found = False
            # 1. Exact Match
            for council in councils:
                if council['name'] == target_name:
                    found = True
                    update_council(council, new_url)
                    modified_count += 1
                    print(f"  [FIXED] {target_name} -> RSS")
                    break
            
            # 2. Smart Fuzzy Match
            if not found:
                target_norm = normalize_name(target_name)
                best_match = None
                best_score = 0
                
                for council in councils:
                    council_norm = normalize_name(council['name'])
                    
                    if target_norm == council_norm:
                        score = 1.0
                    elif target_norm in council_norm or council_norm in target_norm:
                         if len(target_norm) > 3 and len(council_norm) > 3:
                             score = 0.9
                         else:
                             score = 0
                    else:
                        score = difflib.SequenceMatcher(None, target_norm, council_norm).ratio()
                    
                    if score > 0.8 and score > best_score:
                        best_score = score
                        best_match = council
                
                if best_match:
                    found = True
                    update_council(best_match, new_url)
                    modified_count += 1
                    print(f"  [FIXED-FUZZY] {best_match['name']} (Report: {target_name}) -> RSS")

            if not found:
                print(f"  [MISSING] Could not find council: {target_name}")

        if modified_count > 0:
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"  Saved {json_path}")

if __name__ == "__main__":
    fixes = get_ssr_list()
    print(f"Found {len(fixes)} fixes in report.")
    apply_fixes(fixes)

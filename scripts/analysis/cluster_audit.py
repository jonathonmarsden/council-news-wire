import json
import os
import re
from collections import defaultdict
from urllib.parse import urlparse

STATES_DIR = 'states'
RISKY_SELECTOR_REGEX = r'(col-|row|container|clearfix|div\.content|div\.body)'

def load_all_councils():
    councils = []
    for state in os.listdir(STATES_DIR):
        state_path = os.path.join(STATES_DIR, state)
        if not os.path.isdir(state_path):
            continue
        
        json_path = os.path.join(state_path, 'councils.json')
        if not os.path.exists(json_path):
            continue
            
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                for c in data.get('councils', []):
                    c['state'] = state
                    councils.append(c)
        except Exception as e:
            print(f"Error loading {json_path}: {e}")
    return councils

def analyze_clusters(councils):
    clusters = defaultdict(list)
    
    # 1. Vendor Signatures
    signatures = {
        'OpenCities': r'(opencities|oc-)',
        'Squiz': r'squiz',
        'LGHub (QLD)': r'(/About-Council/(Publications|Media)|/Our-Council/News-Media)',
        'Kentico/Alyka': r'(ksearch|/city-and-council/news|/your-city/news)',
        'Civica': r'civica',
        'Datascape': r'datascape'
    }
    
    for c in councils:
        url = c.get('news_url', '')
        # Check against signatures
        matched = False
        for label, pattern in signatures.items():
            if re.search(pattern, url, re.IGNORECASE):
                clusters[label].append(c)
                matched = True
                break
        
        # Fallback: Group by Path Similarity
        if not matched:
            path = urlparse(url).path
            if path == '/news' or path == '/news/':
                clusters['Generic /news'].append(c)
            elif path.startswith('/news-and-events'):
                clusters['/news-and-events'].append(c)
            else:
                # Group by first 2 segments
                parts = path.strip('/').split('/')
                if len(parts) >= 2:
                    sig = f"/{parts[0]}/{parts[1]}"
                    clusters[sig].append(c)

    return clusters

def analyze_selectors(councils):
    risky = []
    for c in councils:
        selectors = [
            c.get('item_selector', ''),
            c.get('title_selector', ''),
            c.get('date_selector', ''),
            c.get('link_selector', '')
        ]
        
        # Also check nested selectors dict if it exists
        if 'selectors' in c:
            selectors.extend(c['selectors'].values())
            
        for s in selectors:
            if s and re.search(RISKY_SELECTOR_REGEX, s):
                risky.append({
                    'id': c['id'],
                    'state': c['state'],
                    'scraper': c.get('scraper'),
                    'bad_selector': s
                })
                break 
    return risky

def main():
    councils = load_all_councils()
    print(f"Loaded {len(councils)} councils.")
    
    # Run Analyses
    clusters = analyze_clusters(councils)
    risky_selectors = analyze_selectors(councils)
    
    # Generate Report
    print("\n=== CLUSTER ANALYSIS ===")
    for label, items in sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True):
        if len(items) > 3 and label != 'Generic /news': # Only show meaningful clusters
            print(f"\nCluster: {label} ({len(items)} councils)")
            # Sample a few
            for i in items[:3]:
                print(f" - {i['id']} ({i['state']}): {i['news_url']}")
                
    print("\n\n=== RISKY SELECTOR AUDIT ===")
    print(f"Found {len(risky_selectors)} councils using generic/layout selectors ({RISKY_SELECTOR_REGEX}).")
    for r in risky_selectors:
        print(f"[{r['state'].upper()}] {r['id']} ({r['scraper']}): {r['bad_selector']}")

if __name__ == "__main__":
    main()

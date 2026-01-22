import json
import os
from collections import defaultdict

STATES_DIR = 'states'

def analyze_state(state):
    config_path = os.path.join(STATES_DIR, state, 'councils.json')
    if not os.path.exists(config_path):
        return None
    
    with open(config_path, 'r') as f:
        data = json.load(f)
        if isinstance(data, dict) and 'councils' in data:
            councils = data['councils']
        elif isinstance(data, list):
            councils = data
        else:
            # print(f"Skipping {state}: unknown format")
            return None
        
    if not isinstance(councils, list):
        print(f"Skipping {state}: root is not a list")
        return None

    # Debug: Check first item
    if len(councils) > 0 and not isinstance(councils[0], dict):
        print(f"Skipping {state}: items are not dicts (found {type(councils[0])})")
        return None
    
    stats = {
        'total': len(councils),
        'enabled': sum(1 for c in councils if c.get('enabled', True)),
        'scrapers': defaultdict(int),
        'use_curl': sum(1 for c in councils if c.get('use_curl', False)),
        'mobile_mode': sum(1 for c in councils if c.get('mobile_mode', False)),
        'catalyst': 0, # explicit count
        'rss': 0,
        'custom': 0
    }
    
    for c in councils:
        scraper = c.get('scraper', 'card_scraper')
        if scraper == 'catalyst_scraper':
            stats['catalyst'] += 1
        elif scraper == 'rss_scraper':
            stats['rss'] += 1
        elif scraper not in ['card_scraper', 'curl_scraper', 'rss_scraper', 'catalyst_scraper']:
             # checking generic customs
             stats['custom'] += 1
        
        stats['scrapers'][scraper] += 1
        
    return stats

def main():
    states = sorted([d for d in os.listdir(STATES_DIR) if os.path.isdir(os.path.join(STATES_DIR, d))])
    
    all_data = []
    
    headers = ["State", "Total", "Enabled", "Card", "RSS", "Catalyst", "Custom", "WAF (Curl)", "Mobile"]
    
    for state in states:
        stats = analyze_state(state)
        if stats:
            row = [
                state.upper(),
                stats['total'],
                f"{stats['enabled']} ({stats['enabled']/stats['total']*100:.1f}%)",
                stats['scrapers'].get('card_scraper', 0) + stats['scrapers'].get('curl_scraper', 0), # grouping generic card
                stats['rss'],
                stats['catalyst'],
                stats['custom'], # Just use the counter
                stats['use_curl'],
                stats['mobile_mode']
            ]
            all_data.append(row)
            
    # print(tabulate(all_data, headers=headers, tablefmt="github"))
    
    # Manual Markdown Table
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in all_data:
        print("| " + " | ".join(str(x) for x in row) + " |")

    # Debug WA
    with open('states/wa/councils.json', 'r') as f:
        data = json.load(f)
        wa_councils = data.get('councils', []) if isinstance(data, dict) else data
        disabled = [c['name'] for c in wa_councils if not c.get('enabled', True)]
        print(f"\nDisabled WA Councils ({len(disabled)}): {', '.join(disabled)}")

if __name__ == "__main__":
    main()

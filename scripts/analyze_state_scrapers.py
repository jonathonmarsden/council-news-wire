import json
import os
from pathlib import Path
import collections

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def analyze_scraper_types():
    stats = {} # state -> {scraper_type: count, total: count}
    
    states_dir = PROJECT_ROOT / 'states'
    
    for state_dir in states_dir.iterdir():
        if not state_dir.is_dir() or state_dir.name.startswith('_'):
            continue
            
        state_code = state_dir.name
        councils_file = state_dir / 'councils.json'
        
        if councils_file.exists():
            stats[state_code] = collections.defaultdict(int)
            stats[state_code]["total"] = 0
            
            try:
                with open(councils_file, 'r') as f:
                    data = json.load(f)
                    councils = data.get('councils', [])
                    
                    for c in councils:
                        scraper_type = c.get('scraper', 'card_scraper')
                        stats[state_code][scraper_type] += 1
                        stats[state_code]["total"] += 1
                        
            except Exception as e:
                print(f"Error reading {state_code}: {e}")

    print("State Scraper Analysis:")
    for state, data in sorted(stats.items()):
        print(f"\n{state.upper()}:")
        for k, v in data.items():
            if k != "total":
                print(f"  - {k}: {v}")
        print(f"  Total: {data['total']}")

if __name__ == "__main__":
    analyze_scraper_types()

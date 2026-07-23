import json
import os
from pathlib import Path

def audit_wa_scrapers():
    file_path = Path(__file__).resolve().parents[1] / 'states' / 'wa' / 'councils.json'
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    councils = data.get('councils', [])
    naked_count = 0
    naked_councils = []
    
    print(f"Auditing {len(councils)} WA councils...")
    
    for council in councils:
        if not council.get('enabled', False):
            continue
            
        scraper_type = council.get('scraper')
        
        if scraper_type == 'card_scraper':
            # Check for explicit selectors
            has_item = 'item_selector' in council
            has_title = 'title_selector' in council
            has_link = 'link_selector' in council
            
            if not (has_item and has_title and has_link):
                naked_count += 1
                naked_councils.append(council['name'])
                
    print(f"\nFound {naked_count} 'naked' CardScraper configs in WA.")
    print("Councils needing attention:")
    for name in naked_councils:
        print(f"- {name}")

if __name__ == "__main__":
    audit_wa_scrapers()

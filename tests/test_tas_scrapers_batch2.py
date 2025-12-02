
import json
import os
import sys
from bs4 import BeautifulSoup

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_tas_scrapers_batch2():
    config_path = 'states/tas/councils.json'
    with open(config_path, 'r') as f:
        config = json.load(f)

    councils = config['councils']
    
    # Map council IDs to their debug files
    debug_files = {
        'central-coast': 'debug_central_coast.html'
    }
    
    for council in councils:
        council_id = council['id']
        if council_id in debug_files and os.path.exists(debug_files[council_id]):
            print(f"Testing {council['name']}...")
            with open(debug_files[council_id], 'r') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            items = soup.select(council['item_selector'])
            print(f"  Found {len(items)} items with selector '{council['item_selector']}'")
            
            if len(items) > 0:
                item = items[0]
                title = item.select_one(council['title_selector'])
                date = item.select_one(council['date_selector'])
                link = item.select_one(council['link_selector'])
                
                print(f"  Title: {title.get_text(strip=True) if title else 'NOT FOUND'}")
                print(f"  Date: {date.get_text(strip=True) if date else 'NOT FOUND'}")
                print(f"  Link: {link['href'] if link and link.has_attr('href') else 'NOT FOUND'}")
            else:
                print("  NO ITEMS FOUND")
            print("-" * 20)

if __name__ == "__main__":
    test_tas_scrapers_batch2()

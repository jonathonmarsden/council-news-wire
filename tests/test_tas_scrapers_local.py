
import json
import os
import sys
from bs4 import BeautifulSoup

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_tas_scrapers():
    config_path = 'states/tas/councils.json'
    with open(config_path, 'r') as f:
        config = json.load(f)

    councils = config['councils']
    
    # Map council IDs to their debug files
    debug_files = {
        'hobart': 'debug_hobart.html',
        'launceston': 'debug_launceston.html',
        'clarence': 'debug_clarence.html',
        'burnie': 'debug_burnie.html',
        'kingborough': 'debug_kingborough.html',
        'huon-valley': 'debug_huon_valley.html',
        'west-tamar': 'debug_west_tamar.html',
        'glenorchy': 'debug_glenorchy.html',
        'devonport': 'debug_devonport.html',
        'meander-valley': 'debug_meander.html'
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
                
                # Handle link selector being 'a' (the item itself might be the link)
                if council['link_selector'] == 'a' and item.name == 'a':
                    link = item
                elif council['link_selector'] == 'a':
                     link = item.find('a')

                print(f"  Title: {title.get_text(strip=True) if title else 'NOT FOUND'}")
                print(f"  Date: {date.get_text(strip=True) if date else 'NOT FOUND'}")
                print(f"  Link: {link['href'] if link and link.has_attr('href') else 'NOT FOUND'}")
            else:
                print("  NO ITEMS FOUND")
            print("-" * 20)

if __name__ == "__main__":
    test_tas_scrapers()

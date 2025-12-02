import sys
import os
import json
from bs4 import BeautifulSoup
import requests

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import load_state_config, get_scraper

def debug_council(council_id, state_code):
    print(f"\n--- Debugging {council_id} ({state_code}) ---")
    try:
        state_data = load_state_config(state_code)
        council = next((c for c in state_data['councils'] if c['id'] == council_id), None)
        
        if not council:
            print(f"Council {council_id} not found in {state_code}")
            return

        print(f"URL: {council['news_url']}")
        print(f"Scraper: {council.get('scraper')}")
        
        scraper = get_scraper(council)
        
        # Run the scraper
        articles = scraper.scrape()
        print(f"Found {len(articles)} articles")
        
        for i, article in enumerate(articles[:3]):
            print(f"\nArticle {i+1}:")
            print(f"  Title: {article.title}")
            print(f"  Date: {article.date}")
            print(f"  URL: {article.url}")
            
        # If no dates found, let's try to fetch the raw HTML and see what's going on
        if articles and not any(a.date for a in articles):
            print("\n[DEBUG] No dates found. Fetching raw HTML to inspect...")
            response = requests.get(council['news_url'], verify=False, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Test configured selectors
            if council.get('item_selector'):
                print(f"\nTesting item_selector: {council['item_selector']}")
                items = soup.select(council['item_selector'])
                print(f"Found {len(items)} items")
                
                if items and council.get('date_selector'):
                    print(f"Testing date_selector: {council['date_selector']} on first item")
                    date_elem = items[0].select_one(council['date_selector'])
                    if date_elem:
                        print(f"Date element found: {date_elem}")
                        print(f"Date text: {date_elem.get_text(strip=True)}")
                    else:
                        print("Date element NOT found in first item")

            # Print the first few potential date elements
            print("\nPotential date elements found in HTML:")
            for tag in ['time', 'span', 'div', 'p']:
                elements = soup.find_all(tag, class_=lambda x: x and ('date' in x.lower() or 'time' in x.lower() or 'published' in x.lower()))
                for el in elements[:3]:
                    print(f"  <{tag} class='{el.get('class')}'>: {el.get_text(strip=True)}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/debug_broken_scrapers.py <council_id> <state_code>")
        sys.exit(1)
        
    debug_council(sys.argv[1], sys.argv[2])

import sys
import os
# Add project root to path (3 levels up from scripts/debug/script.py)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.scrapers import ScraperFactory
import json
import time

def debug_cairns():
    with open('states/qld/councils.json', 'r') as f:
        data = json.load(f)
        
    cairns_config = next(c for c in data['councils'] if c['id'] == 'cairns')
    
    print("Scraping Cairns (Run 1)...")
    scraper = ScraperFactory.create_scraper(cairns_config)
    articles1 = scraper.scrape()
    
    if not articles1:
        print("No articles found!")
        return

    print(f"Found {len(articles1)} articles.")
    print(f"Sample URL 1: {articles1[0].url}")
    
    print("\nWaiting 5 seconds...")
    time.sleep(5)
    
    print("Scraping Cairns (Run 2)...")
    scraper2 = ScraperFactory.create_scraper(cairns_config)
    articles2 = scraper2.scrape()
    
    print(f"Found {len(articles2)} articles.")
    print(f"Sample URL 2: {articles2[0].url}")
    
    if articles1[0].url == articles2[0].url:
        print("\n✅ URLs match.")
    else:
        print("\n❌ URLs DO NOT match!")
        print(f"1: {articles1[0].url}")
        print(f"2: {articles2[0].url}")

if __name__ == "__main__":
    debug_cairns()

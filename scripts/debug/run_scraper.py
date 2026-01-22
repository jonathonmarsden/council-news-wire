import sys
import os
import asyncio
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.scrapers.factory import ScraperFactory
from core.database import Database
from core.utils import setup_logging

async def test_scraper(council_id):
    setup_logging()
    # Just basic stdout logger for now
    
    # Find council config
    config = None
    
    # Search in states/
    for root, dirs, files in os.walk('states'):
        if 'councils.json' in files:
            path = os.path.join(root, 'councils.json')
            try:
                with open(path) as f:
                    data = json.load(f)
                    for c in data['councils']:
                        if c['id'] == council_id:
                            config = c
                            break
            except Exception as e:
                print(f"Error reading {path}: {e}")
            if config: break
    
    if not config:
        print(f"Council {council_id} not found.")
        return

    print(f"Testing scraper for {config['name']} ({council_id})...")
    print(f"Config: impersonate={config.get('impersonate')}, scraper={config.get('scraper')}")
    
    # Force generic scraper if it's generic? Factory handles it.
    try:
        scraper = ScraperFactory.create_scraper(config)
    except Exception as e:
        print(f"Factory Error: {e}")
        return

    if not scraper:
        print("Failed to create scraper.")
        return
        
    print(f"Using scraper class: {scraper.__class__.__name__}")
    
    try:
        articles = scraper.scrape()
        print(f"Found {len(articles)} articles.")
        for a in articles[:1]:
            print(f"- {a.title} ({a.date})")
            print(f"  Url: {a.url}")
            print("  Fetching content...")
            content = scraper._fetch_with_curl(a.url, use_proxy=True)
            if content:
                print(f"  Content Length: {len(content)}")
                if "impersonate" in config:
                     print("  (Fetched used impersonate settings)")
            else:
                print("  Failed to fetch content.")
    except Exception as e:
        print(f"Scrape Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_scraper.py <council_id>")
        sys.exit(1)
    
    asyncio.run(test_scraper(sys.argv[1]))

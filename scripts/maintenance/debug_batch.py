import json
import os
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.scrapers import ScraperFactory
from core.scrapers.base import BaseScraper

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_council_config(council_id):
    # Find the config for this council
    import glob
    state_files = glob.glob("states/*/councils.json")
    for fpath in state_files:
        with open(fpath, 'r') as f:
            data = json.load(f)
            for c in data.get('councils', []):
                if c['id'] == council_id:
                    return c
    return None

def debug_council(council_id):
    print(f"\n=== Debugging {council_id} ===")
    config = load_council_config(council_id)
    if not config:
        print(f"Config not found for {council_id}")
        return

    print(f"URL: {config['news_url']}")
    print(f"Scraper: {config.get('scraper', 'default')}")
    
    try:
        scraper = ScraperFactory.create_scraper(config)
        
        # 1. Fetch Content
        print("Fetching content...")
        content = scraper.fetch_page(config['news_url'])
        if not content:
            print("Failed to fetch content.")
            return
            
        # 2. Save HTML
        save_path = Path(f"debug_html/{council_id}.html")
        save_path.parent.mkdir(exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Saved HTML to {save_path}")
        
        # 3. Run Scrape
        print("Running scrape...")
        articles = scraper.scrape()
        print(f"Found {len(articles)} articles.")
        
        if len(articles) == 0:
            print("⚠️  STILL EMPTY")
        else:
            print("✅  FOUND ARTICLES (Maybe they were just old?)")
            for a in articles[:3]:
                print(f"  - {a.title} ({a.date})")
                
    except Exception as e:
        print(f"Error: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Debug specific councils.')
    parser.add_argument('--councils', nargs='+', help='List of council IDs to debug')
    args = parser.parse_args()

    if args.councils:
        batch = args.councils
    else:
        if not os.path.exists("empty_councils.json"):
            print("empty_councils.json not found.")
            return
            
        with open("empty_councils.json", "r") as f:
            empty_councils = json.load(f)
            
        print(f"Loaded {len(empty_councils)} empty councils.")
        
        # Pick first 5
        batch = empty_councils[:5]
    
    print(f"Debugging batch: {batch}")
    
    for cid in batch:
        debug_council(cid)

if __name__ == "__main__":
    main()

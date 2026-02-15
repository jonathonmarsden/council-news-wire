
import sys
import os
import argparse
import asyncio
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scrapers.card import CardScraper
from core.scrapers.rss import RSSScraper
from core.scrapers.factory import ScraperFactory
import json
from pathlib import Path

def load_council_config(council_id):
    """Finds the council config in all state files."""
    states_dir = Path("states")
    for state_file in states_dir.glob("*/councils.json"):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for council in data.get('councils', []):
                    if council['id'] == council_id:
                        return council, state_file
        except Exception as e:
            print(f"Error reading {state_file}: {e}")
    return None, None

def verify_scraper(council_id):
    print(f"=== Verifying {council_id} ===")
    
    config, file_path = load_council_config(council_id)
    if not config:
        print(f"❌ Council ID '{council_id}' not found.")
        return

    print(f"File: {file_path}")
    print(f"URL: {config['news_url']}")
    print(f"Scraper: {config['scraper']}")

    try:
        # Use Factory to create scraper
        scraper = ScraperFactory.create_scraper(config)
        
        print(f"   Running {scraper.__class__.__name__}...")
        articles = scraper.scrape()
        
        print(f"   Found {len(articles)} articles.")
        
        if len(articles) > 0:
            latest = articles[0]
            print(f"   Latest: {latest.title} ({latest.date})")
            print("✅ SCRAPER SUCCESS")
        else:
            print("⚠️ NO ARTICLES FOUND")
            # Print debug info if available
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify a scraper for a specific council")
    parser.add_argument("--council", required=True, help="Council ID (e.g., nsw_georged_river)")
    args = parser.parse_args()
    
    verify_scraper(args.council)

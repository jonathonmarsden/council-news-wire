
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from core.scrapers import ScraperFactory
from dotenv import load_dotenv
import json

load_dotenv()

def verify_swan():
    # Load config
    config_path = PROJECT_ROOT / "states" / "wa" / "councils.json"
    with open(config_path, "r") as f:
        data = json.load(f)
    
    swan_config = next((c for c in data['councils'] if c['id'] == 'swan'), None)
    
    if not swan_config:
        print("Swan config not found!")
        return
        
    print(f"Testing Scraper for: {swan_config['name']}")
    
    scraper = ScraperFactory.create_scraper(swan_config)
    articles = scraper.scrape()
    
    print(f"Found {len(articles)} articles.")
    for article in articles[:3]:
        print(f"- {article.title} ({article.date}) -> {article.url}")

if __name__ == "__main__":
    verify_swan()


import os
import sys
import json
from pathlib import Path
from core.scrapers import RSSScraper

def verify_rss_fix():
    # Test Councils
    tests = [
        {'state': 'nsw', 'id': 'georges-river-council', 'expected_url': 'https://www.georgesriver.nsw.gov.au/Council/Media?rss=News'},
        {'state': 'qld', 'id': 'toowoomba', 'expected_url': 'https://www.tr.qld.gov.au/about-council/news-publications/media-releases?format=feed&type=rss'},
        {'state': 'tas', 'id': 'tasman', 'expected_url': 'https://www.tasman.tas.gov.au/feed/'}
    ]

    print("=== Verifying RSS Fixes ===")
    
    for test in tests:
        print(f"\nTesting {test['id']} ({test['state']})...")
        
        # Load Config
        json_path = f"states/{test['state']}/councils.json"
        with open(json_path, 'r') as f:
            data = json.load(f)
            
        council_config = next((c for c in data['councils'] if c['id'] == test['id']), None)
        
        if not council_config:
            print(f"❌ Could not find config for {test['id']}")
            continue
            
        # Verify Config
        if council_config.get('scraper') != 'rss_scraper':
            print(f"❌ Scraper is not rss_scraper. Got: {council_config.get('scraper')}")
            continue
            
        if council_config.get('news_url') != test['expected_url']:
            print(f"❌ URL mismatch.\n   Expected: {test['expected_url']}\n   Got:      {council_config.get('news_url')}")
            continue
            
        print("✅ Configuration matches.")
        
        # Run Scraper
        print("   Running scraper...")
        try:
            scraper = RSSScraper(
                council_id=council_config['id'],
                council_name=council_config['name'],
                news_url=council_config['news_url']
            )
            articles = scraper.scrape()
            print(f"   Found {len(articles)} articles.")
            if len(articles) > 0:
                print(f"   Latest: {articles[0].title} ({articles[0].date})")
                print("✅ SCRAPER SUCCESS")
            else:
                print("⚠️ SCRAPER RETURNED 0 ARTICLES (Check manually if feed is empty)")
        except Exception as e:
            print(f"❌ SCRAPER FAILED: {e}")

if __name__ == "__main__":
    # Add root to path to allow imports
    sys.path.append(os.getcwd())
    verify_rss_fix()

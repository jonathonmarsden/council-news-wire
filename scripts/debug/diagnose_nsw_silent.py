import sys
print("Starting diagnosis script...")
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import asyncio
from core.scrapers.custom import OpenCitiesScraper
from core.scrapers.card import CardScraper
from core.scrapers.rss import RSSScraper
from bs4 import BeautifulSoup

def test_opencities(name, url):
    print(f"\n--- Testing OpenCities: {name} ---")
    scraper = OpenCitiesScraper(
        council_id="debug_id",
        council_name=name,
        news_url=url,
        selectors={}
    )
    try:
        articles = scraper.scrape()
        print(f"Found {len(articles)} articles.")
        if len(articles) == 0:
            print("  ❌ Zero articles found. Requesting HTML to debug...")
            response = scraper.fetch_page(url)
            if response:
                print(f"  Preview: {response[:200]}")
                if "OpenCities" in response:
                    print("  ✅ 'OpenCities' detected in HTML.")
                else:
                    print("  ⚠️ 'OpenCities' NOT detected in HTML.")
                
                soup = BeautifulSoup(response, 'html.parser')
                # Check for known selectors
                print(f"  .list-item-container count: {len(soup.select('.list-item-container'))}")
                print(f"  .card count: {len(soup.select('.card'))}")
                print(f"  #SearchResult count: {len(soup.select('#SearchResult'))}")
            else:
                print("  ❌ Failed to fetch page.")
    except Exception as e:
        print(f"  ❌ Error: {e}")

def test_card(name, url, selectors):
    print(f"\n--- Testing Card Scraper: {name} ---")
    scraper = CardScraper(
        council_id="debug_id",
        council_name=name,
        news_url=url,
        selectors=selectors
    )
    try:
        articles = scraper.scrape()
        print(f"Found {len(articles)} articles.")
        if len(articles) == 0:
            print(f"  ❌ Zero articles found.")
            response = scraper.fetch_page(url)
            if response:
                soup = BeautifulSoup(response, 'html.parser')
                item_sel = scraper.selectors.get('item_selector')
                if item_sel:
                    print(f"  Item Selector '{item_sel}' matched {len(soup.select(item_sel))} items.")
                else:
                    print("  ⚠️ No item_selector defined!")
            else:
                print("  ❌ Failed to fetch page.")
    except Exception as e:
        print(f"  ❌ Error: {e}")

def test_rss(name, url):
    print(f"\n--- Testing RSS: {name} ---")
    scraper = RSSScraper(
        council_id="debug_id",
        council_name=name,
        rss_url=url,
        news_url=url
    )
    try:
        articles = scraper.scrape()
        print(f"Found {len(articles)} articles.")
    except Exception as e:
        print(f"  ❌ Error: {e}")

def main():
    print("In Main...")
    # 2. Bogan (RSS)
    print("Running Bogan...")
    test_rss("Bogan", "https://www.bogan.nsw.gov.au/news?format=feed&type=rss")
    
    # 1. Lake Macquarie (OpenCities)
    print("Running Lake Macquarie...")
    test_opencities("Lake Macquarie", "https://www.lakemac.com.au/For-residents/History-and-heritage/News")
    
    # 3. Wollondilly (Card) - has NO selectors in JSON, rely on defaults?
    # CardScraper defaults are basically empty. If JSON has no selectors, it fails.
    test_card("Wollondilly", "https://www.wollondilly.nsw.gov.au/News", {})
    
    # 10. Upper Lachlan (OpenCities)
    test_opencities("Upper Lachlan", "https://www.upperlachlan.nsw.gov.au/News")

    # 11. Snowy Valleys (OpenCities)
    test_opencities("Snowy Valleys", "https://www.snowyvalleys.nsw.gov.au/News")

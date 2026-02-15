import sys
print("STEP 1: Sys imported")
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
print("STEP 2: Path appended")

try:
    from core.scrapers.custom import OpenCitiesScraper
    print("STEP 3: OpenCities imported")
    from core.scrapers.card import CardScraper
    print("STEP 4: Card imported")
    from core.scrapers.rss import RSSScraper
    print("STEP 5: RSS imported")
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    sys.exit(1)

def test_rss(name, url):
    print(f"\n--- Testing RSS: {name} ---")
    try:
        scraper = RSSScraper(
            council_id="debug_id",
            council_name=name,
            rss_url=url,
            news_url=url
        )
        print("created scraper")
        articles = scraper.scrape()
        print(f"Found {len(articles)} articles.")
        if len(articles) == 0:
             # Fetch raw feed content to view
             print("debug fetching...")
             raw = scraper.fetch_page(url)
             print(f"Content preview: {raw[:200]}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

def test_opencities(name, url):
    print(f"\n--- Testing OpenCities: {name} ---")
    try:
        scraper = OpenCitiesScraper(
            council_id="debug_id",
            council_name=name,
            news_url=url,
            selectors={}
        )
        print("created scraper")
        articles = scraper.scrape()
        print(f"Found {len(articles)} articles.")
    except Exception as e:
        print(f"  ❌ Error: {e}")

def test_card(name, url, selectors):
    print(f"\n--- Testing Card: {name} ---")
    try:
        scraper = CardScraper(
            council_id="debug_id",
            council_name=name,
            news_url=url,
            selectors=selectors
        )
        print("created scraper")
        articles = scraper.scrape()
        print(f"Found {len(articles)} articles.")
        if len(articles) == 0:
             print("debug fetching...")
             raw = scraper.fetch_page(url)
             if raw:
                 from bs4 import BeautifulSoup
                 soup = BeautifulSoup(raw, 'html.parser')
                 print(f"Title: {soup.title}")
                 if selectors.get('container'):
                     print(f"Found {len(soup.select(selectors['container']))} items via '{selectors['container']}'")
             else:
                 print("Fail to fetch")
    except Exception as e:
        print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    print("STEP 6: Entering Main")
    test_rss("Bogan", "https://www.bogan.nsw.gov.au/news?format=feed&type=rss")
    
    test_opencities("Lake Macquarie", "https://www.lakemac.com.au/For-residents/History-and-heritage/News")
    # Note: Lake Macquarie config has url https://www.lakemac.com.au/For-residents/History-and-heritage/News
    # I suspect this URL is wrong or empty.
    
    test_card("Wollondilly", "https://www.wollondilly.nsw.gov.au/News", {})
    
    test_opencities("Snowy Valleys", "https://www.snowyvalleys.nsw.gov.au/News")
    
    print("STEP 7: Finished")

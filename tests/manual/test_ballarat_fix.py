import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.scrapers import CardScraper

def test_ballarat():
    selectors = {
        "item_selector": ".card.card--news",
        "title_selector": ".title",
        "date_selector": ".date",
        "link_selector": "self"
    }
    
    scraper = CardScraper(
        "ballarat",
        "City of Ballarat",
        "https://www.ballarat.vic.gov.au/news",
        selectors=selectors
    )
    
    print("Scraping Ballarat...")
    articles = scraper.scrape()
    
    print(f"Found {len(articles)} articles")
    for article in articles[:3]:
        print(f"- {article.title} ({article.date})")
        print(f"  URL: {article.url}")

if __name__ == "__main__":
    test_ballarat()

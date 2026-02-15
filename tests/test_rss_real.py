import sys
import os

# Add current directory to path so we can import core
sys.path.append(os.getcwd())

from core.scrapers.rss import RSSScraper

councils = [
    {"id": "cootamundra-gundagai-regional-council", "url": "https://www.cgrc.nsw.gov.au/feed/", "name": "Cootamundra"},
    {"id": "kyogle-council", "url": "https://www.kyogle.nsw.gov.au/feed/", "name": "Kyogle"},
    {"id": "wentworth-shire-council", "url": "https://www.wentworth.nsw.gov.au/feed/", "name": "Wentworth"},
    {"id": "cook", "url": "https://www.cook.qld.gov.au/feed/", "name": "Cook"},
    {"id": "douglas", "url": "https://douglas.qld.gov.au/feed/", "name": "Douglas"},
    {"id": "tablelands", "url": "https://www.trc.qld.gov.au/feed/", "name": "Tablelands"}
]

for c in councils:
    print(f"\nTesting RSSScraper for {c['name']}...")
    scraper = RSSScraper(c['id'], c['name'], c['url'])
    articles = scraper.scrape()
    print(f"Found {len(articles)} articles.")
    if len(articles) > 0:
        print(f"First: {articles[0].title} - {articles[0].url}")

import requests
from bs4 import BeautifulSoup
from datetime import datetime

targets = [
    {
        "id": "bass-coast",
        "url": "https://www.basscoast.vic.gov.au/about-council/news-listing",
        "selectors": {
            "container": "a.news-item",
            "title": ".news-item__title",
            "date": ".news-item__date"
        }
    },
    {
        "id": "towong",
        "url": "https://www.towong.vic.gov.au/1-council/news-and-media/media-releases",
        "selectors": {
            "container": "#news-listing ul li",
            "title": "h2",
            "date": "time"
        }
    }
]

headers = {"User-Agent": "Mozilla/5.0"}

for t in targets:
    print(f"Testing {t['id']}...")
    try:
        r = requests.get(t['url'], headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        items = soup.select(t['selectors']['container'])
        print(f"  Found {len(items)} items")
        
        for i, item in enumerate(items[:3]):
            title_el = item.select_one(t['selectors']['title'])
            date_el = item.select_one(t['selectors']['date'])
            
            title = title_el.get_text(strip=True) if title_el else "NO TITLE"
            date = date_el.get_text(strip=True) if date_el else "NO DATE"
            
            print(f"  [{i}] {title} | {date}")
            
    except Exception as e:
        print(f"  Error: {e}")
    print("-" * 30)

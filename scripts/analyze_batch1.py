import requests
from bs4 import BeautifulSoup

urls = {
    "bayswater": "https://www.bayswater.wa.gov.au/city-and-council/news",
    "belmont": "https://www.belmont.wa.gov.au/community/news-and-updates",
    "cambridge": "https://www.cambridge.wa.gov.au/Town-Council/News"
}

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

for name, url in urls.items():
    try:
        print(f"Fetching {name}...")
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Dump a formatted snippet
        with open(f"debug_{name}_full.html", "w") as f:
            f.write(soup.prettify())
            
        print(f"Saved {name} to debug_{name}_full.html")
        
        # Heuristics
        print(f"--- {name} Suggestions ---")
        # Look for repeating elements with date/title concepts
        articles = soup.find_all(lambda tag: tag.name in ['div', 'article'] and ('news' in (tag.get('class') or []) or 'item' in (tag.get('class') or [])))
        if not articles:
             articles = soup.select('.news-list > div, .news-item, .post, .entry, .card')
        
        print(f"Found {len(articles)} potential items.")
        if articles:
            print(f"Sample First Item Classes: {articles[0].get('class')}")
            
    except Exception as e:
        print(f"Error {name}: {e}")

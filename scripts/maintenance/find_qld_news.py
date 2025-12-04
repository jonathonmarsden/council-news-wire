from curl_cffi import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

councils = [
    {"id": "banana", "url": "https://www.banana.qld.gov.au/"},
    {"id": "carpentaria", "url": "https://www.carpentaria.qld.gov.au/"},
    {"id": "cassowary-coast", "url": "https://www.cassowarycoast.qld.gov.au/"}
]

for council in councils:
    print(f"Checking {council['id']}...")
    try:
        response = requests.get(council['url'], impersonate="chrome120", timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            links = soup.find_all('a', href=True)
            news_links = []
            for link in links:
                href = link['href']
                text = link.get_text(strip=True).lower()
                if 'news' in text or 'media' in text or 'news' in href.lower():
                    full_url = urljoin(council['url'], href)
                    news_links.append((text, full_url))
            
            print(f"Found {len(news_links)} potential news links:")
            # Deduplicate by URL
            seen_urls = set()
            unique_links = []
            for text, url in news_links:
                if url not in seen_urls:
                    unique_links.append((text, url))
                    seen_urls.add(url)

            for text, url in unique_links[:10]: 
                print(f"  - {text}: {url}")
        else:
            print(f"Failed to fetch homepage: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 20)

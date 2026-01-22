import requests
import json
from urllib.parse import urlparse

# Councils to test
councils = [
    {
        "id": "stirling", 
        "url": "https://www.stirling.wa.gov.au/city-and-council/news",
        "api": "https://www.stirling.wa.gov.au/ksearchnews/ksearchresult"
    },
    {
        "id": "bayswater", 
        "url": "https://www.bayswater.wa.gov.au/city-and-council/news",
        "api": "https://www.bayswater.wa.gov.au/aapi/news/search" 
    },
    {
        "id": "swan", 
        "url": "https://www.swan.wa.gov.au/city-and-council/news-and-media",
        "api": "https://www.swan.wa.gov.au/aapi/news/search" 
    },
    {
        "id": "rockingham", 
        "url": "https://www.rockingham.wa.gov.au/your-city/news",
        "api": "https://www.rockingham.wa.gov.au/aapi/news/search" 
    }
]

def test_api(council):
    print(f"\nTesting {council['id']}...")
    
    # Standard KSearch Body
    body = {
        "take": 5,
        "skip": 0,
        "page": 1,
        "pageSize": 5
    }
    
    # Params
    search_param = [
        {"key": "classname", "values": ["AWPT.News"], "or": "true", "operator": "eq"},
        {"key": "searchindexes", "values": ["News"], "or": "true", "operator": "eq"},
         # Note: Stirling uses /city-and-council/news, strictly matching the path might be required
        {"key": "nodealiaspath", "values": [urlparse(council['url']).path], "or": "true", "operator": "eq"}
    ]
    
    search_filter = [
        {"key": "Sort", "values": ["ArticleReleaseDate DESC"], "or": False, "operator": ""}
    ]
    
    parsed = urlparse(council['url'])
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    headers = {
        "Content-Type": "application/json",
        "SearchParam": json.dumps(search_param),
        "SearchFilter": json.dumps(search_filter),
        "Referer": council['url'],
        "Origin": base_url,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    try:
        r = requests.post(council['api'], json=body, headers=headers, timeout=10)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            items = data.get('Data', [])
            print(f"Items found: {len(items)}")
            if len(items) > 0:
                print(f"Sample: {items[0].get('ArticleTitle')}")
        else:
            print("Failed.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    for c in councils:
        test_api(c)

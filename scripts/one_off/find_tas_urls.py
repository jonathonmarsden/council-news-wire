import requests
from bs4 import BeautifulSoup
import re

def find_news_link(base_url):
    print(f"Checking {base_url}...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(base_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for links containing "news", "media", "latest"
        candidates = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text().lower()
            
            if 'news' in href.lower() or 'media' in href.lower() or 'latest' in href.lower():
                candidates.append((text, href))
            elif 'news' in text or 'media' in text:
                candidates.append((text, href))
                
        return candidates
    except Exception as e:
        print(f"Error: {e}")
        return []

def main():
    councils = [
        ("Northern Midlands", "https://northernmidlands.tas.gov.au/"),
        ("Tasman", "https://www.tasman.tas.gov.au/")
    ]
    
    for name, url in councils:
        print(f"\n--- {name} ---")
        links = find_news_link(url)
        for text, href in links[:10]: # Show top 10
            print(f"Found: '{text.strip()}' -> {href}")

if __name__ == "__main__":
    main()

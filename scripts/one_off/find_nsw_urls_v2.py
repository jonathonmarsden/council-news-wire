import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

councils = {
    "Bourke Shire Council": "https://bourke.nsw.gov.au/",
    "Coonamble Shire Council": "https://www.coonambleshire.nsw.gov.au/",
    "Kyogle Council": "https://www.kyogle.nsw.gov.au/",
    "Moree Plains Shire Council": "https://www.mpsc.nsw.gov.au/",
    "Muswellbrook Shire Council": "https://www.muswellbrook.nsw.gov.au/",
    "Narromine Shire Council": "https://www.narromine.nsw.gov.au/",
    "Tenterfield Shire Council": "https://www.tenterfield.nsw.gov.au/",
    "Warren Shire Council": "https://www.warren.nsw.gov.au/"
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
}

def find_news_link(name, base_url):
    try:
        print(f"Scanning {name} ({base_url})...")
        response = requests.get(base_url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"  Failed to load homepage: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)
        
        candidates = []
        for link in links:
            href = link['href']
            text = link.get_text().lower()
            full_url = urljoin(base_url, href)
            
            # Score the link
            score = 0
            if 'news' in href.lower() or 'news' in text:
                score += 2
            if 'media' in href.lower() or 'media' in text:
                score += 1
            if 'latest' in href.lower() or 'latest' in text:
                score += 1
            if 'release' in href.lower():
                score += 1
                
            if score > 0:
                candidates.append((score, full_url, text.strip()))
        
        # Sort by score
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Return top 3
        return candidates[:3]
        
    except Exception as e:
        print(f"  Error: {e}")
        return None

for name, url in councils.items():
    results = find_news_link(name, url)
    if results:
        print(f"  Found candidates for {name}:")
        for score, link, text in results:
            print(f"    [{score}] {link} ('{text}')")
    else:
        print(f"  No candidates found for {name}")
    print("-" * 40)

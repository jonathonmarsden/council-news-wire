import requests
from bs4 import BeautifulSoup

councils = {
    "yarra": "https://www.yarracity.vic.gov.au/news",
    "darebin": "https://www.darebin.vic.gov.au/About-Council/News-and-Media"
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
}

for name, url in councils.items():
    print(f"\n--- Checking {name} at {url} ---")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for potential article containers
            print("Potential article containers:")
            
            # Yarra often uses .card or .listing-item
            # Darebin often uses .list-item or similar
            
            # Dump some headings to see structure
            headings = soup.find_all(['h2', 'h3'])
            for h in headings[:5]:
                print(f"  Heading ({h.name}): {h.get_text(strip=True)}")
                parent = h.parent
                print(f"    Parent: {parent.name} (class: {parent.get('class')})")
                
            # Dump some links with 'news' in href
            print("\n  Links with 'news' or 'media' in href:")
            links = soup.find_all('a', href=True)
            count = 0
            for link in links:
                href = link.get('href')
                if ('/news' in href or '/media' in href) and len(link.get_text(strip=True)) > 10:
                    print(f"    Link: {link.get_text(strip=True)[:50]}... -> {href}")
                    print(f"      Parent: {link.parent.name} (class: {link.parent.get('class')})")
                    count += 1
                    if count > 3: break
                    
    except Exception as e:
        print(f"Error: {e}")

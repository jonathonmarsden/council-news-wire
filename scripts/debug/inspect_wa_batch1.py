import sys
import os
from curl_cffi import requests
from bs4 import BeautifulSoup

def inspect_site(name, url, scraper_type="curl"):
    print(f"\n--- Inspecting {name} ({url}) [Type: {scraper_type}] ---")
    try:
        if scraper_type == "rss":
            response = requests.get(url, impersonate="chrome124", verify=False, timeout=30)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                content = response.text
                if "<rss" in content or "<feed" in content or "<channel" in content:
                    print("Valid RSS/Atom feed detected.")
                    # Show first few lines
                    print(content[:200])
                else:
                    print("RSS feed content not detected.")
                    print(content[:200])
        else:
            response = requests.get(url, impersonate="chrome124", verify=False, timeout=30)
            content = response.text
            soup = BeautifulSoup(content, 'html.parser')
            print(f"Title: {soup.title.string.strip() if soup.title else 'No Title'}")
            
            # Check for common containers
            containers = soup.select('.list-item-container, .news-list, .view-content, .views-row')
            print(f"Found {len(containers)} potential containers (generic check)")
            
            # Check specifics for OpenCities
            if soup.select('.list-item-container article'):
                print("OpenCities structure detected (.list-item-container article)")
            
    except Exception as e:
        print(f"Error fetching: {e}")

# RSS Candidates
inspect_site("Carnamah", "https://www.carnamah.wa.gov.au/news/feed/", "rss")
inspect_site("Coorow", "https://coorow.wa.gov.au/news/rss/", "rss")
inspect_site("Kent", "https://www.kent.wa.gov.au/feed/", "rss")
inspect_site("Three Springs", "https://www.threesprings.wa.gov.au/index.php/our-council/news-archive?format=feed&type=rss", "rss")

# Other Candidates
# inspect_site("Cambridge", "https://www.cambridge.wa.gov.au/About/News", "curl")
# inspect_site("Melville", "https://www.melvillecity.com.au/our-city/news", "curl")

def deep_inspect(name, url):
    print(f"\n--- Deep Inspecting {name} ({url}) ---")
    try:
        response = requests.get(url, impersonate="chrome124", verify=False, timeout=30)
        content = response.text
        soup = BeautifulSoup(content, 'html.parser')
        
        print(f"Title: {soup.title.string.strip() if soup.title else 'No Title'}")
        
        # Check for any 'news' related classes
        news_classes = []
        for tag in soup.find_all(class_=True):
            for cls in tag['class']:
                if 'news' in cls.lower() or 'listing' in cls.lower() or 'item' in cls.lower():
                    if cls not in news_classes:
                        news_classes.append(cls)
        print(f"Potential news classes found (first 10): {news_classes[:10]}")
        
        # Look for titles (h2, h3) and their parents
        print("Looking for headers...")
        for header in soup.select('h2, h3')[:3]:
            print(f"Header: {header.get_text(strip=True)[:50]}")
            parent = header.parent
            print(f"  Parent: {parent.name}.{'.'.join(parent.get('class', []))}")
            grandparent = parent.parent
            if grandparent:
                print(f"  Grandparent: {grandparent.name}.{'.'.join(grandparent.get('class', []))}")

    except Exception as e:
        print(f"Error: {e}")

deep_inspect("Cambridge", "https://www.cambridge.wa.gov.au/About/News")
deep_inspect("Melville", "https://www.melvillecity.com.au/our-city/news/latest-news")
deep_inspect("Karratha", "https://www.karratha.wa.gov.au/council/news")
deep_inspect("Mosman Park", "https://www.mosmanpark.wa.gov.au/council/council/news-2/")

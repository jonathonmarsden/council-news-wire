import sys
import os
from curl_cffi import requests
from bs4 import BeautifulSoup

def inspect_site(name, url):
    print(f"--- Inspecting {name} ({url}) ---")
    try:
        response = requests.get(url, impersonate="chrome124", verify=False, timeout=30)
        content = response.text
    except Exception as e:
        print(f"Error fetching: {e}")
        return

    soup = BeautifulSoup(content, 'html.parser')

    # Dump the "risky" items
    risky_items = soup.select('.list-item-container, div.list-item-container')
    print(f"Found {len(risky_items)} risky items.")
    if risky_items:
        print("First risky item:")
        print(risky_items[0].prettify()[:1000])
        
        # Check if there is an <article> tag inside
        article = risky_items[0].find('article')
        if article:
            print(f"Found ARTICLE tag inside! Class: {article.get('class')}")
        else:
            print("No ARTICLE tag inside.")

inspect_site("Hobart", "https://www.hobartcity.com.au/Council/News-publications-and-announcements/Latest-news")
inspect_site("Logan", "https://www.logan.qld.gov.au/about-council/media-releases")

import sys
import os
from curl_cffi import requests
from bs4 import BeautifulSoup

def inspect_site(name, url):
    print(f"--- Inspecting {name} ({url}) ---")
    try:
        response = requests.get(url, impersonate="chrome124", verify=False, timeout=30)
        content = response.text
        if response.status_code != 200:
            print(f"Failed to fetch: {response.status_code}")
            return
    except Exception as e:
        print(f"Error fetching: {e}")
        return

    soup = BeautifulSoup(content, 'html.parser')

    # Dump the "risky" items to see what they look like
    items = soup.select('div.col-sm-7')
    if items:
        print(f"Found {len(items)} items using div.col-sm-7")
        print(items[0].prettify()[:1000])
        # Look for parents
        parent = items[0].find_parent()
        if parent:
            print("\nParent:")
            print(parent.prettify()[:500])
            grandparent = parent.find_parent()
            if grandparent:
                print("\nGrandparent:")
                print(grandparent.prettify()[:500])
    else:
        print("No items found with current selector.")
        # Try to find a better container
        print("Dumping body structure:")
        main = soup.select_one('main') or soup.find('body')
        if main:
            print(main.prettify()[:2000])

inspect_site("Albany", "https://www.albany.wa.gov.au/news/")
inspect_site("Bridgetown", "https://www.bridgetown.wa.gov.au/news/")

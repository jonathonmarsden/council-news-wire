from curl_cffi import requests
from bs4 import BeautifulSoup

url = "https://www.cityofadelaide.com.au/news"
response = requests.get(url, impersonate="chrome110")
soup = BeautifulSoup(response.content, 'html.parser')

# Find the first news title
title = soup.find('h4', string=lambda t: t and "Four towers" in t)
if title:
    print("Found title:", title)
    # Print parent hierarchy to find the container
    parent = title.parent
    while parent and parent.name != 'body':
        print(f"Parent: {parent.name} class={parent.get('class')}")
        parent = parent.parent
else:
    print("Title not found. Dumping h4s:")
    for h4 in soup.find_all('h4')[:5]:
        print(h4)

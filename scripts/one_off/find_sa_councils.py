import requests
from bs4 import BeautifulSoup
import time
import json
import re
from urllib.parse import urljoin, urlparse

councils = [
    "Adelaide (City of)",
    "Adelaide Hills Council",
    "Adelaide Plains Council",
    "Alexandrina Council",
    "Barossa Council (The)",
    "Barunga West Council",
    "Berri Barmera Council",
    "Burnside (City of)",
    "Campbelltown City Council",
    "Ceduna (District Council of)",
    "Charles Sturt (City of)",
    "Clare and Gilbert Valleys Council",
    "Cleve (District Council of)",
    "Coober Pedy (District Council of)",
    "Coorong District Council",
    "Copper Coast Council",
    "Elliston (District Council of)",
    "Flinders Ranges Council (The)",
    "Franklin Harbour (District Council of)",
    "Gawler (Town of)",
    "Goyder (Regional Council of)",
    "Grant (District Council of)",
    "Holdfast Bay (City of)",
    "Kangaroo Island Council",
    "Karoonda East Murray (District Council of)",
    "Kimba (District Council of)",
    "Kingston District Council",
    "Light Regional Council",
    "Lower Eyre Council",
    "Loxton Waikerie (District Council of)",
    "Marion (City of)",
    "Mid Murray Council",
    "Mitcham (City of)",
    "Mount Barker District Council",
    "Mount Gambier (City of)",
    "Mount Remarkable (District Council of)",
    "Murray Bridge (Rural City of)",
    "Naracoorte Lucindale Council",
    "Northern Areas Council",
    "Norwood Payneham & St Peters (City of)",
    "Onkaparinga (City of)",
    "Orroroo Carrieton (District Council of)",
    "Peterborough (District Council of)",
    "Playford (City of)",
    "Port Adelaide Enfield (City of)",
    "Port Augusta City Council",
    "Port Lincoln (City of)",
    "Port Pirie Regional Council",
    "Prospect (City of)",
    "Renmark Paringa Council",
    "Robe (District Council of)",
    "Roxby Downs (Municipal Council of)",
    "Salisbury (City of)",
    "Southern Mallee District Council",
    "Streaky Bay (District Council of)",
    "Tatiara District Council",
    "Tea Tree Gully (City of)",
    "Tumby Bay (District Council of)",
    "Unley (City of)",
    "Victor Harbor (City of)",
    "Wakefield Regional Council",
    "Walkerville (Town of)",
    "Wattle Range Council",
    "West Torrens (City of)",
    "Whyalla (City of)",
    "Wudinna District Council",
    "Yankalilla (District Council of)",
    "Yorke Peninsula Council"
]

def clean_name(name):
    # Remove (City of), (District Council of), etc. for searching
    name = re.sub(r'\s*\(.*?\)', '', name)
    return name.strip()

def get_kebab_case(name):
    name = clean_name(name)
    return name.lower().replace(' ', '-')

def search_duckduckgo(query):
    url = f"https://html.duckduckgo.com/html/?q={query}"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        results = soup.find_all('a', class_='result__a')
        if results:
            return results[0]['href']
    except Exception as e:
        print(f"Error searching for {query}: {e}")
    return None

def find_news_page(base_url):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
    try:
        resp = requests.get(base_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Look for RSS
        rss_link = None
        links = soup.find_all('link', type=['application/rss+xml', 'application/atom+xml'])
        if links:
            rss_link = urljoin(base_url, links[0]['href'])
        
        if not rss_link:
            # Check a tags for rss
            for a in soup.find_all('a', href=True):
                if 'rss' in a['href'].lower():
                    rss_link = urljoin(base_url, a['href'])
                    break

        # Look for News page
        news_url = base_url
        candidates = ['news', 'media', 'latest-news', 'press', 'media-releases']
        
        found_news = False
        for a in soup.find_all('a', href=True):
            text = a.get_text().lower()
            href = a['href'].lower()
            if any(c in text for c in candidates) or any(c in href for c in candidates):
                # Prioritize "news"
                if 'news' in text or 'news' in href:
                    news_url = urljoin(base_url, a['href'])
                    found_news = True
                    break
        
        if not found_news:
            # Try common paths
            common_paths = ['/news', '/latest-news', '/media-releases', '/council-news']
            for path in common_paths:
                try:
                    test_url = urljoin(base_url, path)
                    r = requests.head(test_url, headers=headers, timeout=5)
                    if r.status_code == 200:
                        news_url = test_url
                        break
                except:
                    pass

        return news_url, rss_link

    except Exception as e:
        print(f"Error visiting {base_url}: {e}")
        return base_url, None

results = []

for council in councils:
    print(f"Processing {council}...")
    search_name = clean_name(council)
    website = search_duckduckgo(f"{search_name} Council South Australia official website")
    
    if website:
        print(f"  Found website: {website}")
        news_url, rss_url = find_news_page(website)
        print(f"  News URL: {news_url}")
        if rss_url:
            print(f"  RSS URL: {rss_url}")
        
        entry = {
            "id": get_kebab_case(council),
            "name": council,
            "news_url": news_url,
            "scraper": "rss_scraper" if rss_url else "card_scraper",
            "enabled": True
        }
        if rss_url:
            entry["rss_url"] = rss_url
            
        results.append(entry)
    else:
        print(f"  Could not find website for {council}")
        results.append({
            "id": get_kebab_case(council),
            "name": council,
            "news_url": "",
            "scraper": "card_scraper",
            "enabled": False
        })
    
    time.sleep(2) # Be nice

output = {"councils": results}
with open('sa_councils.json', 'w') as f:
    json.dump(output, f, indent=4)

print("Done. Saved to sa_councils.json")

import sys
import os
import asyncio
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.scrapers.factory import ScraperFactory

async def fetch_html(council_id):
    # Find council config
    config = None
    for root, dirs, files in os.walk('states'):
        if 'councils.json' in files:
            path = os.path.join(root, 'councils.json')
            try:
                with open(path) as f:
                    data = json.load(f)
                    for c in data['councils']:
                        if c['id'] == council_id:
                            config = c
                            break
            except Exception as e:
                print(f"Error reading {path}: {e}")
            if config: break
    
    if not config:
        print(f"Council {council_id} not found.")
        return

    print(f"Fetching HTML for {config['name']} using {config.get('scraper')}...")
    
    scraper = ScraperFactory.create_scraper(config)
    
    # We need to access the fetch method directly or use the scraper's session
    # Most scrapers have a setup method or internal session
    # We will try to use the _fetch_content method or _fetch_with_curl if available
    # Or just use the requests/curl_cffi logic manually if needed, but better to use the scraper's method
    
    url = config['news_url']
    content = None
    
    try:
        if hasattr(scraper, 'fetch_content'):
             content = scraper.fetch_content(url)
        elif hasattr(scraper, '_fetch_with_curl'):
             content = scraper._fetch_with_curl(url) 
        elif hasattr(scraper, 'session'):
             resp = scraper.session.get(url)
             content = resp.text
        else:
             print("Could not find a fetch method on scraper.")
             return
    except Exception as e:
        print(f"Error fetching: {e}")
        return

    if content:
        filename = f"debug_{council_id}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Saved {len(content)} bytes to {filename}")
    else:
        print("No content fetched (None returned).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_html.py <council_id>")
        sys.exit(1)
    
    asyncio.run(fetch_html(sys.argv[1]))

#!/usr/bin/env python3
"""
RSS Feed Discovery Tool

Iterates through configured councils and checks their home/news pages for:
1. <link rel="alternate" type="application/rss+xml"> tags
2. Common RSS file patterns (feed.xml, rss.xml, /rss)
3. 'RSS' text links

Usage:
    python3 scripts/find_rss_feeds.py --state vic
"""

import argparse
import json
import os
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import concurrent.futures

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scrapers import BaseScraper

def load_councils(state):
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'states', state, 'councils.json')
    if not os.path.exists(config_path):
        return []
    with open(config_path, 'r') as f:
        return json.load(f).get('councils', [])

def check_council_for_rss(council):
    url = council['news_url']
    # Also check root domain
    root_url = '/'.join(url.split('/')[:3])
    
    found_feeds = []
    
    # Helper to check a URL
    def check_url(target_url):
        try:
            # Use a simple request with timeout
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
            response = requests.get(target_url, headers=headers, timeout=10)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            feeds = []
            
            # 1. Check <link> tags
            for link in soup.find_all('link', rel='alternate'):
                if link.get('type') in ['application/rss+xml', 'application/atom+xml']:
                    feeds.append(urljoin(target_url, link.get('href')))
                    
            # 2. Check <a> tags with "RSS" text
            for a in soup.find_all('a', href=True):
                if 'rss' in a.text.lower() or 'atom' in a.text.lower() or 'feed' in a.text.lower():
                    href = a.get('href')
                    if href.endswith('.xml') or 'rss' in href:
                        feeds.append(urljoin(target_url, href))
                        
            return list(set(feeds))
        except Exception as e:
            return []

    # Check News URL
    found_feeds.extend(check_url(url))
    
    # Check Root URL if different
    if root_url != url.rstrip('/'):
        found_feeds.extend(check_url(root_url))
        
    return list(set(found_feeds))

def main():
    parser = argparse.ArgumentParser(description='Find RSS feeds for councils')
    parser.add_argument('--state', type=str, required=True, help='State code (vic, nsw, qld)')
    parser.add_argument('--concurrency', type=int, default=10, help='Concurrent checks')
    args = parser.parse_args()
    
    councils = load_councils(args.state)
    print(f"Checking {len(councils)} councils in {args.state.upper()} for RSS feeds...")
    
    results = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_to_council = {executor.submit(check_council_for_rss, c): c for c in councils}
        
        for future in concurrent.futures.as_completed(future_to_council):
            council = future_to_council[future]
            try:
                feeds = future.result()
                if feeds:
                    print(f"✅ {council['name']}: Found {len(feeds)} feeds")
                    results[council['name']] = feeds
                else:
                    # print(f"❌ {council['name']}: No feeds found")
                    pass
            except Exception as e:
                print(f"Error checking {council['name']}: {e}")
                
    # Report
    print(f"\n=== RSS Discovery Report ({args.state.upper()}) ===")
    print(f"Found feeds for {len(results)} / {len(councils)} councils.")
    
    report_path = f"RSS_DISCOVERY_{args.state.upper()}.md"
    with open(report_path, 'w') as f:
        f.write(f"# RSS Discovery: {args.state.upper()}\n\n")
        for name, feeds in results.items():
            f.write(f"## {name}\n")
            for feed in feeds:
                f.write(f"- {feed}\n")
            f.write("\n")
            
    print(f"Saved report to {report_path}")

if __name__ == "__main__":
    main()

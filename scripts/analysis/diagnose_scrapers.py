#!/usr/bin/env python3
"""
Scraper Diagnosis Tool

Iterates through "Dead" scrapers (0 articles) and determines the cause of failure:
1. HTTP 404/Connection Error
2. Empty Selector (Page loads but no articles found)
3. WAF/403 (Blocked)
4. RSS Available (Alternative found)

Auto-fixes councils by switching to RSS if a feed is discovered.
"""

import json
import os
from sqlalchemy import text
import sys
import requests
import concurrent.futures
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from core.config import CONFIG_PATHS
from core.database import Database

# Common headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-AU,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def load_all_councils():
    """Load all configured councils from JSON files."""
    councils = {}
    
    for state, config_path in CONFIG_PATHS.items():
        if config_path.exists():
            with open(config_path, 'r') as f:
                try:
                    data = json.load(f)
                    for c in data.get('councils', []):
                        c['state'] = state
                        c['config_path'] = config_path # Store path for updates
                        councils[c['id']] = c
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode {config_path}")
    return councils

def get_dead_councils():
    """Identify councils with 0 articles."""
    db = Database()
    councils = load_all_councils()
    dead_councils = []
    
    with db.get_session() as session:
        # Get all council IDs that have at least one article
        result = session.execute(text("SELECT DISTINCT council_id FROM articles"))
        active_ids = {row[0] for row in result.fetchall()}
        
    for c_id, config in councils.items():
        if not config.get('enabled', True):
            continue
            
        if c_id not in active_ids:
            dead_councils.append(config)
            
    return dead_councils

def check_council(council):
    """
    Diagnose a single council.
    Returns a dict with diagnosis results.
    """
    url = council.get('news_url')
    if not url:
        return {'council': council, 'status': 'MISSING_URL', 'details': 'No news_url defined'}
        
    try:
        response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        
        # Check for WAF/Blocking
        if response.status_code == 403:
            return {'council': council, 'status': 'WAF_BLOCK', 'details': '403 Forbidden (Likely Cloudflare/Incapsula)'}
        
        # Check for 404
        if response.status_code == 404:
            return {'council': council, 'status': 'HTTP_404', 'details': 'Page not found'}
            
        if response.status_code != 200:
            return {'council': council, 'status': f'HTTP_{response.status_code}', 'details': f'Status code {response.status_code}'}
            
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check for RSS Feed
        rss_link = soup.find('link', type='application/rss+xml')
        if rss_link and rss_link.get('href'):
            rss_url = urljoin(url, rss_link.get('href'))
            return {'council': council, 'status': 'RSS_FOUND', 'details': rss_url, 'rss_url': rss_url}
            
        # Check Selector (if defined)
        # Some councils might be RSS-only already, but if they are dead, maybe the RSS URL is wrong?
        # Assuming we are diagnosing HTML scrapers mostly.
        selector = council.get('selector')
        if selector:
            elements = soup.select(selector)
            if not elements:
                return {'council': council, 'status': 'EMPTY_SELECTOR', 'details': f'Selector "{selector}" found 0 items'}
            else:
                # If selector works, why is it dead? Maybe parsing logic failed?
                return {'council': council, 'status': 'UNKNOWN_FAILURE', 'details': f'Selector found {len(elements)} items, but DB is empty. Parsing issue?'}
        
        return {'council': council, 'status': 'NO_SELECTOR', 'details': 'Page loads, but no selector defined'}

    except requests.exceptions.RequestException as e:
        return {'council': council, 'status': 'CONNECTION_ERROR', 'details': str(e)}
    except Exception as e:
        return {'council': council, 'status': 'ERROR', 'details': str(e)}

def apply_rss_fix(council, rss_url):
    """Update the council config to use RSS."""
    config_path = council['config_path']
    
    # Read current config
    with open(config_path, 'r') as f:
        data = json.load(f)
        
    # Find and update the council
    updated = False
    for c in data['councils']:
        if c['id'] == council['id']:
            c['news_url'] = rss_url
            # Remove HTML specific fields if they exist
            c.pop('selector', None)
            c.pop('title_selector', None)
            c.pop('date_selector', None)
            c.pop('body_selector', None)
            updated = True
            break
            
    if updated:
        with open(config_path, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    return False

def main():
    print("🔍 Identifying Dead Scrapers...")
    dead_councils = get_dead_councils()
    print(f"Found {len(dead_councils)} dead councils.")
    
    print("🚀 Starting Diagnosis (Concurrency: 10)...")
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_council = {executor.submit(check_council, c): c for c in dead_councils}
        
        completed = 0
        for future in concurrent.futures.as_completed(future_to_council):
            completed += 1
            if completed % 10 == 0:
                print(f"Progress: {completed}/{len(dead_councils)}")
            results.append(future.result())
            
    # Categorize Results
    by_status = {}
    rss_fixes = []
    
    for r in results:
        status = r['status']
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(r)
        
        if status == 'RSS_FOUND':
            rss_fixes.append(r)
            
    # Apply Auto-Fixes
    print(f"\n🛠️ Found {len(rss_fixes)} RSS Feeds. Applying fixes...")
    fixed_count = 0
    for fix in rss_fixes:
        if apply_rss_fix(fix['council'], fix['rss_url']):
            fixed_count += 1
            print(f"  ✅ Fixed {fix['council']['name']} -> {fix['rss_url']}")
            
    # Generate Report
    report_path = Path(project_root) / 'DEAD_SCRAPERS_REPORT.md'
    with open(report_path, 'w') as f:
        f.write(f"# 💀 Dead Scrapers Diagnosis ({len(dead_councils)} Total)\n\n")
        
        f.write("## 📊 Summary\n")
        for status, items in by_status.items():
            f.write(f"- **{status}**: {len(items)}\n")
        f.write(f"- **Auto-Fixed (RSS)**: {fixed_count}\n\n")
        
        f.write("## 🛠️ Auto-Fixed (Switched to RSS)\n")
        if rss_fixes:
            f.write("| State | Council | New RSS URL |\n")
            f.write("|-------|---------|-------------|\n")
            for item in rss_fixes:
                c = item['council']
                f.write(f"| {c['state'].upper()} | {c['name']} | {item['rss_url']} |\n")
        else:
            f.write("No RSS feeds found.\n")
            
        f.write("\n## ⚠️ WAF Blocked (403)\n")
        f.write("Likely need `curl_cffi` or residential proxy.\n\n")
        f.write("| State | Council | URL |\n")
        f.write("|-------|---------|-----|\n")
        for item in by_status.get('WAF_BLOCK', []):
            c = item['council']
            f.write(f"| {c['state'].upper()} | {c['name']} | {c['news_url']} |\n")
            
        f.write("\n## ❌ HTTP 404 / Connection Error\n")
        f.write("URL is likely changed. Needs manual update.\n\n")
        f.write("| State | Council | URL | Error |\n")
        f.write("|-------|---------|-----|-------|\n")
        for status in ['HTTP_404', 'CONNECTION_ERROR', 'MISSING_URL']:
            for item in by_status.get(status, []):
                c = item['council']
                f.write(f"| {c['state'].upper()} | {c['name']} | {c['news_url']} | {item['details']} |\n")
                
        f.write("\n## 🔍 Empty Selector (Page Loads, No Items)\n")
        f.write("Selector needs update.\n\n")
        f.write("| State | Council | URL | Selector |\n")
        f.write("|-------|---------|-----|----------|\n")
        for item in by_status.get('EMPTY_SELECTOR', []):
            c = item['council']
            f.write(f"| {c['state'].upper()} | {c['name']} | {c['news_url']} | `{c.get('selector')}` |\n")

        f.write("\n## ❓ Unknown Failures\n")
        f.write("Selector matched items, but DB is empty. Logic error?\n\n")
        f.write("| State | Council | Details |\n")
        f.write("|-------|---------|---------|\n")
        for item in by_status.get('UNKNOWN_FAILURE', []):
            c = item['council']
            f.write(f"| {c['state'].upper()} | {c['name']} | {item['details']} |\n")

    print(f"\nReport generated at {report_path}")

if __name__ == "__main__":
    # Suppress InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    main()

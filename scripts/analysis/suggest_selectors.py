#!/usr/bin/env python3
"""
Selector Suggestion Tool

Analyzes the HTML of "Dead" councils (that are not WAF blocked) to suggest potential CSS selectors.
"""

import json
import os
import sys
import requests
from sqlalchemy import text
import concurrent.futures
from bs4 import BeautifulSoup
from pathlib import Path
from collections import Counter

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from core.config import CONFIG_PATHS
from core.database import Database

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

def load_all_councils():
    councils = {}
    for state, config_path in CONFIG_PATHS.items():
        if config_path.exists():
            with open(config_path, 'r') as f:
                try:
                    data = json.load(f)
                    for c in data.get('councils', []):
                        c['state'] = state
                        councils[c['id']] = c
                except json.JSONDecodeError:
                    pass
    return councils

def get_dead_councils():
    db = Database()
    councils = load_all_councils()
    dead_councils = []
    
    with db.get_session() as session:
        result = session.execute(text("SELECT DISTINCT council_id FROM articles"))
        active_ids = {row[0] for row in result.fetchall()}
        
    for c_id, config in councils.items():
        if not config.get('enabled', True):
            continue
        if c_id not in active_ids:
            dead_councils.append(config)
    return dead_councils

def analyze_page(council):
    url = council.get('news_url')
    if not url:
        return None
        
    try:
        response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if response.status_code != 200:
            return {'council': council, 'error': f"HTTP {response.status_code}"}
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        suggestions = []
        
        # 1. Look for <article> tags
        articles = soup.find_all('article')
        if articles:
            suggestions.append(f"Found {len(articles)} <article> tags. Try selector: 'article'")
            
        # 2. Look for common class names
        common_classes = ['news-item', 'news-list-item', 'blog-post', 'post', 'entry', 'item', 'card', 'news-card']
        for cls in common_classes:
            elements = soup.find_all(class_=lambda x: x and cls in x)
            if elements:
                # Get the most specific class
                counts = Counter([c for e in elements for c in e.get('class', []) if cls in c])
                best_class = counts.most_common(1)[0][0]
                suggestions.append(f"Found {len(elements)} elements with class containing '{cls}'. Try selector: '.{best_class}'")

        # 3. Look for repeated structures with links and dates
        # This is complex, but we can look for lists
        lists = soup.find_all(['ul', 'ol'])
        for lst in lists:
            items = lst.find_all('li')
            if len(items) > 2:
                # Check if items contain links
                links = [i.find('a') for i in items if i.find('a')]
                if len(links) > 2:
                    # Check if parent has a meaningful class
                    parent_class = lst.get('class')
                    if parent_class:
                        suggestions.append(f"Found list with {len(items)} items. Try selector: '.{'.'.join(parent_class)} li'")
        
        return {
            'council': council,
            'suggestions': suggestions,
            'current_selector': council.get('selector')
        }

    except Exception as e:
        return {'council': council, 'error': str(e)}

def main():
    print("🔍 Analyzing Dead Scrapers for Selector Suggestions...")
    dead_councils = get_dead_councils()
    
    # Skip those we just fixed with curl (unless they are still dead, but we haven't run a scrape yet)
    # Actually, we should check all dead ones.
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_council = {executor.submit(analyze_page, c): c for c in dead_councils}
        
        completed = 0
        for future in concurrent.futures.as_completed(future_to_council):
            completed += 1
            if completed % 10 == 0:
                print(f"Progress: {completed}/{len(dead_councils)}")
            results.append(future.result())
            
    # Generate Report
    report_path = Path(project_root) / 'SELECTOR_SUGGESTIONS.md'
    with open(report_path, 'w') as f:
        f.write("# 🕵️ Selector Suggestions\n\n")
        
        for res in results:
            if not res: continue
            
            c = res['council']
            f.write(f"## {c['name']} ({c['state'].upper()})\n")
            f.write(f"- **URL**: {c['news_url']}\n")
            f.write(f"- **Current Selector**: `{res.get('current_selector')}`\n")
            
            if 'error' in res:
                f.write(f"- ❌ **Error**: {res['error']}\n")
            elif res['suggestions']:
                f.write("- **Suggestions**:\n")
                for s in res['suggestions']:
                    f.write(f"    - {s}\n")
            else:
                f.write("- ⚠️ No obvious suggestions found.\n")
            
            f.write("\n")
            
    print(f"\nReport generated at {report_path}")

if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    main()

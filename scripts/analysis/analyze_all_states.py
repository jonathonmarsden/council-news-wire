import json
import os
import glob
from collections import Counter, defaultdict
from pathlib import Path
import sqlite3
import datetime

def analyze_states():
    root_dir = Path("states")
    states = [d.name for d in root_dir.iterdir() if d.is_dir() and not d.name.startswith('_')]
    
    total_stats = {
        'total': 0,
        'enabled': 0,
        'disabled': 0,
        'scrapers': Counter(),
        'by_state': {}
    }
    
    disabled_reasons = defaultdict(list)
    
    print(f"Analyzing {len(states)} states: {', '.join(states)}\n")
    
    # Try connecting to DB for last success data
    db_path = "bot.db"
    db_data = {}
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Get success counts/dates if table exists
            try:
                # Check for last_posted or similar stats if available, 
                # but usually we might just check scraped_articles count per council if available.
                # The schema isn't fully known, so I'll be conservative. 
                # I'll check 'articles' table.
                cursor.execute("SELECT council_id, COUNT(*), MAX(found_date) FROM articles GROUP BY council_id")
                rows = cursor.fetchall()
                for r in rows:
                    db_data[r[0]] = {'count': r[1], 'last_seen': r[2]}
            except Exception as e:
                print(f"DB Error (articles table): {e}")
            conn.close()
    except Exception as e:
        print(f"DB connection failed: {e}")

    for state in sorted(states):
        config_path = root_dir / state / "councils.json"
        if not config_path.exists():
            continue
            
        with open(config_path, 'r') as f:
            try:
                data = json.load(f)
                councils = data.get('councils', [])
            except json.JSONDecodeError:
                print(f"Error reading {config_path}")
                continue
                
        state_stats = {
            'total': len(councils),
            'enabled': 0,
            'disabled': 0,
            'scrapers': Counter(),
            'disabled_list': []
        }
        
        for c in councils:
            cid = c.get('id')
            is_enabled = c.get('enabled', True)
            scraper_type = c.get('scraper', 'card_scraper') # Default
            
            # Normalization
            if c.get('use_curl'):
                scraper_type = 'curl_scraper'
            
            state_stats['scrapers'][scraper_type] += 1
            total_stats['scrapers'][scraper_type] += 1
            
            if is_enabled:
                state_stats['enabled'] += 1
                total_stats['enabled'] += 1
            else:
                state_stats['disabled'] += 1
                total_stats['disabled'] += 1
                reason = c.get('disabled_reason', 'No reason provided')
                state_stats['disabled_list'].append((cid, reason))
                disabled_reasons[reason].append(f"{state}/{cid}")

        total_stats['total'] += state_stats['total']
        total_stats['by_state'][state] = state_stats

        # Print State Summary
        print(f"=== {state.upper()} ===")
        print(f"  Total: {state_stats['total']}")
        print(f"  Enabled: {state_stats['enabled']} ({state_stats['enabled']/state_stats['total']*100:.1f}%)")
        print(f"  Disabled: {state_stats['disabled']}")
        if state_stats['disabled'] > 0:
            print("  Disabled Examples:")
            for cid, reason in state_stats['disabled_list'][:3]:
                print(f"    - {cid}: {reason}")
            if len(state_stats['disabled_list']) > 3:
                print(f"    ... and {len(state_stats['disabled_list'])-3} more")
        print(f"  Scrapers: {dict(state_stats['scrapers'])}")
        print("")

    print("=== GLOBAL SUMMARY ===")
    print(f"Total Councils: {total_stats['total']}")
    print(f"Enabled: {total_stats['enabled']} ({total_stats['enabled']/total_stats['total']*100:.1f}%)")
    print(f"Disabled: {total_stats['disabled']}")
    print("Scraper Distribution:")
    for k, v in total_stats['scrapers'].most_common():
        print(f"  {k}: {v}")

    print("\n=== TOP DISABLED REASONS ===")
    grouped_reasons = Counter()
    for r, councils in disabled_reasons.items():
        # Clean up reason for grouping (simple heuristic)
        simple_reason = r.split('.')[0].split('(')[0].strip()
        grouped_reasons[simple_reason] += len(councils)
    
    for r, count in grouped_reasons.most_common(10):
        print(f"  {count}: {r}")

if __name__ == "__main__":
    analyze_states()

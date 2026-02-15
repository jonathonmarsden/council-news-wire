#!/usr/bin/env python3
"""
Monitor script to identify "Quiet Councils".
Logs to Discord if a council has not had a NEW article in > 7 days.
Helps distinguish between "Broken Scraper" and "No News".
"""

import sys
import os
import json
from datetime import datetime, timedelta
from typing import Dict
from sqlalchemy import func

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core.database import Database
from core.models import Article
from discord_logger import log_generic_report, DISCORD_WEBHOOK_URL

def load_councils(root_path: str) -> Dict[str, Dict]:
    """Load all enabled councils."""
    councils = {}
    states_dir = os.path.join(root_path, 'states')
    if not os.path.exists(states_dir):
        print(f"Error: states dir not found at {states_dir}")
        return {}
        
    for state in os.listdir(states_dir):
        state_path = os.path.join(states_dir, state)
        if not os.path.isdir(state_path):
            continue
        
        json_path = os.path.join(state_path, 'councils.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    
                    council_list = data
                    if isinstance(data, dict):
                        council_list = data.get('councils', [])
                        
                    if not isinstance(council_list, list):
                        continue

                    for c in council_list:
                        if isinstance(c, dict) and c.get('enabled', True):
                            councils[c['id']] = c
            except Exception as e:
                print(f"Error reading {json_path}: {e}")
    return councils

def check_quiet_councils():
    db = Database()
    root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    enabled_councils = load_councils(root_path)
    
    print(f"Checking {len(enabled_councils)} enabled councils...")
    
    # Get last article time for all councils
    last_seen_map = {}
    with db.get_session() as session:
        # We query first_seen_at because it tracks when WE scaped it.
        # Alternatively we could use 'date' if we parsed it reliably, but first_seen_at is safer.
        results = session.query(Article.council_id, func.max(Article.first_seen_at)).group_by(Article.council_id).all()
        for cid, last_seen in results:
            last_seen_map[cid] = last_seen
            
    quiet_councils = []
    threshold = datetime.now() - timedelta(days=7)
    
    for cid, council in enabled_councils.items():
        last_seen = last_seen_map.get(cid)
        
        # Condition 1: Never seen (and enabled)
        if not last_seen:
            quiet_councils.append({
                'name': council['name'],
                'id': cid,
                'status': 'Never Scraped',
                'days': 9999
            })
            continue
            
        # Condition 2: Seen > 7 days ago
        if last_seen < threshold:
            days = (datetime.now() - last_seen).days
            quiet_councils.append({
                'name': council['name'],
                'id': cid,
                'status': f"Last news {last_seen.strftime('%Y-%m-%d')}",
                'days': days
            })

    # Sort by days quiet (descending)
    quiet_councils.sort(key=lambda x: x['days'], reverse=True)
    
    print(f"Found {len(quiet_councils)} quiet councils.")
    
    # Log to Discord
    if quiet_councils:
        # Create summary
        report_lines = []
        for c in quiet_councils[:25]: # Limit to top 25 to avoid limit
            day_str = "Never" if c['days'] == 9999 else f"{c['days']} days"
            report_lines.append(f"• **{c['name']}**: {day_str}")
        
        if len(quiet_councils) > 25:
            report_lines.append(f"... and {len(quiet_councils) - 25} more.")
            
        description = "\n".join(report_lines)
        
        if DISCORD_WEBHOOK_URL:
            log_generic_report(
                f"🤫 Quiet Council Report ({len(quiet_councils)} > 7 days)",
                f"The following councils have added no new news in > 7 days. This might mean no news, or a broken scraper.\n\n{description}",
                color=16776960 # Yellow
            )
            print("Logged to Discord.")
        else:
            print("Discord webhook not configured.")
    else:
        print("No quiet councils found! (Everything is fresh)")

if __name__ == "__main__":
    check_quiet_councils()

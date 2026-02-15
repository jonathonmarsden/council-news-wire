import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List
import sqlalchemy
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Load environment to ensure DB url is set
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from core.database import Database
from core.models import CouncilHealth, Article

import re

def slugify(text: str) -> str:
    """Normalize text to match DB keys (approximate)."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text) # Remove quotes etc
    text = re.sub(r'\s+', '-', text)
    return text.strip('-')

def get_configured_councils() -> Dict[str, Dict]:
    """Load all configured councils from JSON files."""
    councils = {}
    states_dir = PROJECT_ROOT / 'states'
    for state_dir in states_dir.glob('*'):
        if not state_dir.is_dir() or state_dir.name.startswith('_'):
            continue
        
        config_file = state_dir / 'councils.json'
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    for c in data.get('councils', []):
                        name = c['name']
                        slug = slugify(name)
                        councils[slug] = {
                            'original_name': name,
                            'state': state_dir.name,
                            'url': c.get('url'),
                            'config': c
                        }
            except Exception as e:
                print(f"Error loading {config_file}: {e}", file=sys.stderr)
    return councils

def generate_report():
    db = Database()
    session = db.get_session()
    
    configured = get_configured_councils()
    
    # query health
    stmt = select(CouncilHealth)
    health_records = session.scalars(stmt).all()
    
    db_councils = {h.council_id: h for h in health_records}
    
    # Calculate stats
    total_configured = len(configured)
    total_tracked = len(db_councils)
    
    failing = []
    stale = []
    empty_streak = []
    healthy = []
    missing_from_db = []
    
    now = datetime.utcnow()
    stale_threshold = timedelta(days=2) 
    
    # Cross reference
    for slug, data in configured.items():
        if slug not in db_councils:
            # Try some fuzzy matching or just report missing
            missing_from_db.append({'name': data['original_name'], 'state': data['state'], 'slug': slug})
            continue
            
        health = db_councils[slug]
        name = data['original_name']
        
        # Check failing
        if health.consecutive_failures > 0:
            failing.append({
                'name': name,
                'state': data['state'],
                'failures': health.consecutive_failures,
                'last_fail': health.last_failure_at
            })
            continue
            
        # Check stale (not run successfully recently)
        last_success = health.last_success_at
        if not last_success or (now - last_success) > stale_threshold:
            stale.append({
                'name': name,
                'state': data['state'],
                'last_success': str(last_success) if last_success else "Never"
            })
            continue
            
        # Check empty streak (running validation but finding nothing)
        if health.consecutive_empty_runs > 15:
            empty_streak.append({
                'name': name,
                'state': data['state'],
                'empty_runs': health.consecutive_empty_runs
            })
            continue
            
        healthy.append(name)

    # Sort
    failing.sort(key=lambda x: x['state'])
    stale.sort(key=lambda x: x['state'])
    empty_streak.sort(key=lambda x: x['state'])
    missing_from_db.sort(key=lambda x: x['state'])

    # Print Report
    print(f"# Council Scraper Health Report")
    print(f"Generated at: {now.isoformat()}")
    print(f"Total Configured: {total_configured}")
    print(f"Total in DB: {total_tracked}")
    print(f"Healthy: {len(healthy)}")
    print(f"Failing: {len(failing)}")
    print(f"Stale (>48h): {len(stale)}")
    print(f"Empty Streak (>15): {len(empty_streak)}")
    print(f"Missing from DB: {len(missing_from_db)}")
    
    if failing:
        print("\n## 🔴 Failing Scrapers (Errors)")
        print("| State | Council | Failures | Last Failure |")
        print("|-------|---------|----------|--------------|")
        for x in failing:
            print(f"| {x['state']} | {x['name']} | {x['failures']} | {x['last_fail']} |")
            
    if stale:
        print("\n## 🟠 Stale Scrapers (No success > 48h)")
        print("| State | Council | Last Success |")
        print("|-------|---------|--------------|")
        for x in stale:
            print(f"| {x['state']} | {x['name']} | {x['last_success']} |")
            
    if empty_streak:
        print("\n## 🟡 High Empty Streak (Possible Selector Issues)")
        print("| State | Council | Empty Runs |")
        print("|-------|---------|------------|")
        for x in empty_streak:
            print(f"| {x['state']} | {x['name']} | {x['empty_runs']} |")

    if missing_from_db:
        print("\n## ⚪ Missing from DB (Never Run)")
        for x in missing_from_db:
            print(f"- [{x['state']}] {x['name']}")

if __name__ == "__main__":
    try:
        generate_report()
    except Exception as e:
        print(f"Critical Error: {e}")
        import traceback
        traceback.print_exc()

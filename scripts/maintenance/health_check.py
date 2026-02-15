#!/usr/bin/env python3
"""
Health Check Script

Analyzes the database and configuration to identify:
1. Broken scrapers (no articles in > 30 days)
2. Silent failures (councils in config but not in DB)
3. Activity stats
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import select, func

# Add project root to path
# Go up 3 levels: scripts/maintenance/health_check.py -> scripts/maintenance -> scripts -> root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from core.config import CONFIG_PATHS
from core.database import Database
from core.models import Article

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
                        councils[c['id']] = c
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode {config_path}")
    return councils

def generate_report():
    db = Database()
    session = db.get_session()
    configured_councils = load_all_councils()
    
    print(f"Analyzing {len(configured_councils)} configured councils...")
    
    # Get last seen date for each council
    stats_stmt = select(
        Article.council_id,
        Article.state,
        func.max(Article.first_seen_at),
        func.count(Article.id)
    ).group_by(Article.council_id, Article.state)

    db_stats = {
        row[0]: {
            "council_id": row[0],
            "state": row[1],
            "last_seen": row[2],
            "article_count": row[3]
        }
        for row in session.execute(stats_stmt).all()
    }
    
    # Analysis
    healthy = []
    stale = [] # > 30 days
    dead = [] # Never seen
    
    now = datetime.now()
    
    for c_id, config in configured_councils.items():
        if not config.get('enabled', True):
            continue
            
        stats = db_stats.get(c_id)
        
        if not stats:
            dead.append(config)
            continue
            
        last_seen = stats['last_seen']
        if not last_seen:
            dead.append(config)
            continue
            
        days_since = (now - last_seen).days
        
        info = {
            'name': config['name'],
            'state': config['state'],
            'days_since': days_since,
            'last_seen': last_seen.isoformat(),
            'count': stats['article_count']
        }
        
        if days_since > 30:
            stale.append(info)
        else:
            healthy.append(info)
            
    # Output Report
    from core.config import PROJECT_ROOT
    report_file = PROJECT_ROOT / 'HEALTH_REPORT.md'
    
    with open(report_file, 'w') as f:
        f.write(f"# 🏥 Bot Health Report ({now.strftime('%Y-%m-%d')})\n\n")
        
        f.write("## 📊 Summary\n")
        f.write(f"- **Total Configured**: {len(configured_councils)}\n")
        f.write(f"- **Healthy (<30 days)**: {len(healthy)} ✅\n")
        f.write(f"- **Stale (>30 days)**: {len(stale)} ⚠️\n")
        f.write(f"- **Dead (Never scraped)**: {len(dead)} ❌\n\n")
        
        f.write("## ⚠️ Stale Scrapers (>30 Days)\n")
        f.write("| State | Council | Days Since | Last Article |\n")
        f.write("|-------|---------|------------|--------------|\n")
        for item in sorted(stale, key=lambda x: x['days_since'], reverse=True):
            f.write(f"| {item['state'].upper()} | {item['name']} | {item['days_since']} | {item['last_seen']} |\n")
            
        f.write("\n## ❌ Dead Scrapers (Never found articles)\n")
        f.write("| State | Council | URL |\n")
        f.write("|-------|---------|-----|\n")
        for item in dead:
            f.write(f"| {item['state'].upper()} | {item['name']} | {item['news_url']} |\n")
            
    print(f"Report generated at {report_file}")
    print(f"Summary: {len(healthy)} Healthy, {len(stale)} Stale, {len(dead)} Dead")

    session.close()

if __name__ == "__main__":
    generate_report()

#!/usr/bin/env python3
"""
Daily Report Script.

Generates a summary of:
- Total articles scraped today.
- Number of active vs. failed councils.
- List of councils that triggered the Circuit Breaker (DISABLED).
"""

import sqlite3
import os
import sys
from datetime import datetime, timedelta

def get_db_path():
    # Default to bot.db in the parent directory
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bot.db')

def generate_report():
    db_path = os.environ.get('DB_PATH', get_db_path())
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print(f"=== Daily Report: {datetime.now().strftime('%Y-%m-%d')} ===\n")
    
    # 1. Articles Scraped Today
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cursor = conn.execute(
        "SELECT COUNT(*) as c FROM articles WHERE first_seen_at >= ?", 
        (today_start,)
    )
    articles_today = cursor.fetchone()['c']
    print(f"📰 Articles Scraped Today: {articles_today}")
    
    # 2. Council Health Stats
    cursor = conn.execute("SELECT COUNT(*) as c FROM council_health")
    total_tracked = cursor.fetchone()['c']
    
    cursor = conn.execute("SELECT COUNT(*) as c FROM council_health WHERE is_disabled = 1")
    disabled_count = cursor.fetchone()['c']
    
    print(f"🏢 Councils Tracked: {total_tracked}")
    print(f"✅ Healthy Councils: {total_tracked - disabled_count}")
    print(f"❌ Disabled Councils: {disabled_count}")
    
    # 3. List Disabled Councils
    if disabled_count > 0:
        print("\n⚠️  DISABLED COUNCILS (Action Required):")
        cursor = conn.execute(
            "SELECT council_id, consecutive_failures, last_failure_at, disabled_at FROM council_health WHERE is_disabled = 1"
        )
        for row in cursor:
            print(f"  - {row['council_id']}")
            print(f"    Failures: {row['consecutive_failures']}")
            print(f"    Last Failure: {row['last_failure_at']}")
            print(f"    Disabled At: {row['disabled_at']}")
            print("")
    else:
        print("\n✨ No councils are currently disabled.")

    conn.close()

if __name__ == "__main__":
    generate_report()

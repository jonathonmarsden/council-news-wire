import sqlite3
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_backlog_freshness():
    conn = sqlite3.connect('bot.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all unposted articles
    cursor.execute("SELECT id, title, date, council_id, state FROM articles WHERE posted_at IS NULL")
    rows = cursor.fetchall()
    
    now = datetime.now()
    cutoff_7_days = now - timedelta(days=7)
    cutoff_30_days = now - timedelta(days=30)
    
    fresh_count = 0
    stale_count = 0 # 7-30 days
    old_count = 0   # > 30 days
    no_date_count = 0
    future_count = 0
    
    print(f"Analyzing {len(rows)} unposted articles...")
    print(f"Current Date: {now.strftime('%Y-%m-%d')}")
    print("-" * 60)
    
    for row in rows:
        date_str = row['date']
        if not date_str:
            no_date_count += 1
            continue
            
        try:
            # Handle ISO format 2025-11-27T00:00:00
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str)
            else:
                # Try simple date format YYYY-MM-DD
                dt = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Make naive for comparison
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
                
            if dt > now + timedelta(days=1): # Allow 1 day buffer for timezone weirdness
                future_count += 1
                # print(f"Future: {row['title']} ({date_str})")
            elif dt >= cutoff_7_days:
                fresh_count += 1
            elif dt >= cutoff_30_days:
                stale_count += 1
            else:
                old_count += 1
                # if old_count <= 5:
                #    print(f"Old: {row['title']} ({date_str}) - {row['council_id']}")
        except ValueError:
            no_date_count += 1
            print(f"Bad Date Format: {date_str}")

    print(f"[Fresh] (< 7 days):      {fresh_count}")
    print(f"[Stale] (7-30 days):    {stale_count}")
    print(f"[Old] (> 30 days):       {old_count}")
    print(f"[Future] Future Dates:          {future_count}")
    print(f"[Unknown] No/Bad Date:           {no_date_count}")
    
    if old_count > 0:
        print("\nTop 'Old' Councils:")
        cursor.execute("""
            SELECT council_id, COUNT(*) as c 
            FROM articles 
            WHERE posted_at IS NULL 
            AND date < date('now', '-30 days')
            GROUP BY council_id 
            ORDER BY c DESC 
            LIMIT 5
        """)
        for row in cursor.fetchall():
            print(f"- {row['council_id']}: {row['c']}")

if __name__ == "__main__":
    analyze_backlog_freshness()

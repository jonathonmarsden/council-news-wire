from datetime import datetime, timedelta
import sys
import os
from sqlalchemy import select, text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Database
from core.models import Article

def analyze_backlog_freshness():
    db = Database()
    session = db.get_session()
    
    # Get all unposted articles
    rows = session.execute(
        select(Article.id, Article.title, Article.date, Article.council_id, Article.state)
        .where(Article.posted_at.is_(None))
    ).all()
    
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
        date_str = row[2]
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
        rows = session.execute(
            text(
                """
                SELECT council_id, COUNT(*) as c
                FROM articles
                WHERE posted_at IS NULL
                AND date < (current_date - interval '30 days')::text
                GROUP BY council_id
                ORDER BY c DESC
                LIMIT 5
                """
            )
        ).fetchall()
        for row in rows:
            print(f"- {row[0]}: {row[1]}")

    session.close()

if __name__ == "__main__":
    analyze_backlog_freshness()

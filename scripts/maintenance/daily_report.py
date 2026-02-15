#!/usr/bin/env python3
"""
Daily Report Script.

Generates a summary of:
- Total articles scraped today.
- Number of active vs. failed councils.
- List of councils that triggered the Circuit Breaker (DISABLED).
"""

from datetime import datetime, timedelta
from sqlalchemy import select, func

from core.database import Database
from core.models import Article, CouncilHealth

def generate_report():
    db = Database()
    session = db.get_session()
    
    print(f"=== Daily Report: {datetime.now().strftime('%Y-%m-%d')} ===\n")
    
    # 1. Articles Scraped Today
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    articles_stmt = select(func.count(Article.id)).where(Article.first_seen_at >= today_start)
    articles_today = session.execute(articles_stmt).scalar() or 0
    print(f"📰 Articles Scraped Today: {articles_today}")
    
    # 2. Council Health Stats
    total_tracked = session.execute(select(func.count(CouncilHealth.council_id))).scalar() or 0
    disabled_count = session.execute(
        select(func.count(CouncilHealth.council_id)).where(CouncilHealth.is_disabled.is_(True))
    ).scalar() or 0
    
    print(f"🏢 Councils Tracked: {total_tracked}")
    print(f"✅ Healthy Councils: {total_tracked - disabled_count}")
    print(f"❌ Disabled Councils: {disabled_count}")
    
    # 3. List Disabled Councils
    if disabled_count > 0:
        print("\n⚠️  DISABLED COUNCILS (Action Required):")
        disabled_stmt = select(
            CouncilHealth.council_id,
            CouncilHealth.consecutive_failures,
            CouncilHealth.last_failure_at,
            CouncilHealth.disabled_at
        ).where(CouncilHealth.is_disabled.is_(True))
        for row in session.execute(disabled_stmt).all():
            print(f"  - {row[0]}")
            print(f"    Failures: {row[1]}")
            print(f"    Last Failure: {row[2]}")
            print(f"    Disabled At: {row[3]}")
            print("")
    else:
        print("\n✨ No councils are currently disabled.")

    session.close()

if __name__ == "__main__":
    generate_report()


from datetime import datetime, timedelta
from sqlalchemy import select, func

from core.database import Database
from core.models import Article

def generate_report():
    db = Database()
    session = db.get_session()
    now = datetime.now()
    one_day_ago = now - timedelta(days=1)
    seven_days_ago = now - timedelta(days=7)

    report = {
        "generated_at": now.isoformat(),
        "stats": {},
        "councils": {},
        "recent_posts": []
    }

    # 1. Overall Stats (Last 24h)
    collected_stmt = select(Article.state, func.count(Article.id)).where(
        Article.first_seen_at > one_day_ago
    ).group_by(Article.state)
    report["stats"]["collected_24h"] = {
        row[0]: row[1] for row in session.execute(collected_stmt).all()
    }

    posted_stmt = select(Article.state, func.count(Article.id)).where(
        Article.posted_at > one_day_ago
    ).group_by(Article.state)
    report["stats"]["posted_24h"] = {
        row[0]: row[1] for row in session.execute(posted_stmt).all()
    }

    # 2. Specific Council Checks
    target_councils = [
        'warren-shire-council', # NSW - Fixed title parsing
        'cairns',               # QLD - Duplicate issues
        'glamorgan-spring-bay', # TAS - Fixed RSS
        'break-o-day',          # TAS - Fixed RSS
        'brighton',             # TAS - Fixed RSS
        'circular-head',        # TAS - Android User-Agent fix
        'kingborough',          # TAS
        'huon-valley'           # TAS
    ]
    
    print("\n=== Target Council Status (Last 7 Days) ===")
    for council_id in target_councils:
        counts_stmt = select(
            func.count(Article.id),
            func.max(Article.first_seen_at)
        ).where(
            Article.council_id == council_id,
            Article.first_seen_at > seven_days_ago
        )
        count_row = session.execute(counts_stmt).first()

        posted_stmt = select(func.count(Article.id)).where(
            Article.council_id == council_id,
            Article.posted_at > one_day_ago
        )
        posted_24h = session.execute(posted_stmt).scalar() or 0

        print(
            f"{council_id}: {count_row[0]} collected (Last seen: {count_row[1]}), {posted_24h} posted in last 24h"
        )

    # 3. Warren Specific Check (Title Quality)
    print("\n=== Warren Shire Recent Titles ===")
    warren_stmt = select(
        Article.title,
        Article.url,
        Article.posted_at
    ).where(
        Article.council_id == "warren-shire-council"
    ).order_by(Article.id.desc()).limit(5)
    for row in session.execute(warren_stmt).all():
        status = "Posted" if row[2] else "Pending"
        print(f"[{status}] {row[0]}")

    # 4. Total Councils Active
    active_stmt = select(func.count(func.distinct(Article.council_id))).where(
        Article.first_seen_at > seven_days_ago
    )
    active_councils = session.execute(active_stmt).scalar() or 0
    print(f"\nTotal Active Councils (7d): {active_councils}")

    session.close()

if __name__ == "__main__":
    generate_report()

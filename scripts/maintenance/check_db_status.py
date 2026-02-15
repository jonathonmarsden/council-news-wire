import os
import sys
from sqlalchemy import select, func

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from core.database import Database
from core.models import Article

def check_status():
    db = Database()
    session = db.get_session()
    
    # Count total articles
    total = session.execute(select(func.count(Article.id))).scalar() or 0
    
    # Count unposted articles (excluding archived)
    unposted = session.execute(
        select(func.count(Article.id)).where(
            Article.posted_at.is_(None),
            Article.status != 'archived'
        )
    ).scalar() or 0
    
    # Get breakdown by council for unposted
    breakdown = session.execute(
        select(Article.council_id, func.count(Article.id)).where(
            Article.posted_at.is_(None),
            Article.status != 'archived'
        ).group_by(Article.council_id).order_by(func.count(Article.id).desc())
    ).all()
    
    print(f"Total Articles: {total}")
    print(f"Unposted (Backlog): {unposted}")
    print("\nBacklog by Council:")
    for council, count in breakdown:
        print(f"  {council}: {count}")

    session.close()

if __name__ == "__main__":
    check_status()

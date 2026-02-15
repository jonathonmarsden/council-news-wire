import sys
from sqlalchemy import select, func

from core.database import Database
from core.models import Article

# Run this on VPS via ssh
# python3 -c "..."

def get_stats():
    db = Database()
    session = db.get_session()

    rows = session.execute(
        select(
            Article.council_id,
            func.count(Article.id),
            func.max(Article.first_seen_at),
            Article.state
        ).group_by(Article.council_id, Article.state).order_by(Article.state, Article.council_id)
    ).all()

    for row in rows:
        cid, cnt, last, st = row
        last_seen = last.isoformat() if last else "1970-01-01 00:00:00"
        print(f"{cid}|{cnt}|{last_seen}|{st}")

    session.close()

if __name__ == "__main__":
    get_stats()

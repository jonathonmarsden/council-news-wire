import sys
import os
from sqlalchemy import select, delete, or_, func

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Database
from core.models import Article

def cleanup_inner_west():
    db = Database()
    session = db.get_session()

    undated_filter = or_(
        Article.date.is_(None),
        Article.date == '',
        Article.date == 'None'
    )

    count_stmt = select(func.count(Article.id)).where(
        Article.council_id == 'inner-west-council',
        undated_filter
    )
    count = session.execute(count_stmt).scalar() or 0
    print(f"Found {count} undated Inner West articles to delete.")

    if count > 0:
        session.execute(
            delete(Article).where(
                Article.council_id == 'inner-west-council',
                undated_filter
            )
        )
        session.commit()
        print("Deletion complete.")

        remaining_stmt = select(func.count(Article.id)).where(
            Article.council_id == 'inner-west-council'
        )
        remaining = session.execute(remaining_stmt).scalar() or 0
        print(f"Remaining Inner West articles: {remaining}")
    else:
        print("Nothing to delete.")

    session.close()

if __name__ == "__main__":
    cleanup_inner_west()

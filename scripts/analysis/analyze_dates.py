from sqlalchemy import select, func, inspect

from core.database import Database
from core.models import Article

def analyze_dates():
    db = Database()
    session = db.get_session()

    # Check schema
    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("articles")]
    print(f"Columns: {columns}")

    # Count total articles
    total = session.execute(select(func.count(Article.id))).scalar() or 0

    # Count articles with no date
    no_date = session.execute(
        select(func.count(Article.id)).where(
            (Article.date.is_(None)) | (Article.date == '')
        )
    ).scalar() or 0

    print(f"Total Articles: {total}")
    print(f"Articles with No Date: {no_date}")

    # Group by council_id for no date
    rows = session.execute(
        select(Article.council_id, func.count(Article.id)).where(
            (Article.date.is_(None)) | (Article.date == '')
        ).group_by(Article.council_id).order_by(func.count(Article.id).desc()).limit(20)
    ).all()

    print("\nTop Councils with Missing Dates:")
    for row in rows:
        print(f"{row[0]}: {row[1]}")

    session.close()

if __name__ == "__main__":
    analyze_dates()

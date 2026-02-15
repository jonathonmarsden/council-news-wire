import sys
from pathlib import Path
from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[2]))

from core.database import Database
from core.models import Article

def check_warren_titles():
    db = Database()
    session = db.get_session()

    print("Checking Warren Shire Council articles...")
    rows = session.execute(
        select(Article.title, Article.url, Article.date)
        .where(Article.council_id == 'warren-shire-council')
        .order_by(Article.date.desc())
        .limit(10)
    ).all()
    if not rows:
        print("No articles found for Warren Shire Council.")
    
    for row in rows:
        title, url, date = row
        print(f"Date: {date}")
        print(f"Title: {title}")
        print(f"URL: {url}")
        print("-" * 40)

    session.close()

if __name__ == "__main__":
    check_warren_titles()

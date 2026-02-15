import os
import sys
from pathlib import Path
from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[2]))

from core.database import Database
from core.models import Article

def check_cairns_duplicates():
    db = Database()
    session = db.get_session()
    
    print("Checking for duplicates in DB...")
    
    # Find specific title
    title = "EOIs now open for Cairns Children's Festival 2026"
    print(f"Checking for title: {title}")
    
    details_stmt = select(
        Article.id,
        Article.council_id,
        Article.state,
        Article.posted_at,
        Article.posted_to_handle,
        Article.url
    ).where(Article.title == title)
    details = session.execute(details_stmt).all()
    
    if not details:
        print("No articles found with that title.")
    
    for d in details:
        print(
            f"  ID: {d[0]} | State: {d[2]} | Posted: {d[3]} | Handle: {d[4]} | URL: {d[5]}"
        )

    session.close()

if __name__ == "__main__":
    check_cairns_duplicates()

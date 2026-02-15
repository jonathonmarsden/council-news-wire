import sys
from pathlib import Path
from sqlalchemy import select

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.database import Database
from core.models import Article

def reset_act_posts():
    db = Database()
    session = db.get_session()
    
    # Find ALL ACT articles
    articles = session.execute(
        select(
            Article.id,
            Article.title,
            Article.url,
            Article.posted_at,
            Article.status,
            Article.state
        ).where(
            Article.state.in_(['ACT', 'act'])
        ).order_by(Article.id.desc())
    ).all()
    
    if not articles:
        print("No ACT articles found in DB.")
        return

    print(f"Found {len(articles)} ACT articles:")
    for art in articles:
        print(f"[{art[0]}] {art[1]} (State: {art[5]}, Status: {art[4]}, Posted: {art[3]})")

        
    # Do not reset yet, just list
    session.close()

if __name__ == "__main__":
    reset_act_posts()

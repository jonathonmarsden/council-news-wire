import os
import sys
import argparse
from sqlalchemy import select, or_, delete

# Add project root to path
sys.path.append(os.getcwd())

from core.database import Database
from core.models import Article

def cleanup_html_titles(dry_run=True):
    db = Database()
    session = db.get_session()
    
    # Look for titles OR excerpts with HTML tags or entities
    # We check for <, >, &lt;, &gt;, &nbsp;, &amp;
    patterns = ["%<%", "%>%", "%&lt;%", "%&gt;%", "%&nbsp;%", "%&amp;%", "%&#%"]
    title_checks = [Article.title.like(p) for p in patterns]
    excerpt_checks = [Article.excerpt.like(p) for p in patterns]

    stmt = select(
        Article.id,
        Article.council_id,
        Article.title,
        Article.url,
        Article.posted_at,
        Article.status,
        Article.excerpt
    ).where(
        or_(*(title_checks + excerpt_checks)),
        Article.state == 'wa'
    ).order_by(Article.posted_at.desc())

    rows = session.execute(stmt).all()
    
    print(f"Found {len(rows)} WA articles with potential HTML in title or excerpt:")
    
    ids_to_delete = []
    
    for row in rows:
        print(f"ID: {row[0]}")
        print(f"Council: {row[1]}")
        print(f"Title: {row[2]}")
        print(f"Excerpt: {row[6]}")
        print(f"URL: {row[3]}")
        print(f"Posted At: {row[4]}")
        print("-" * 40)
        ids_to_delete.append(row[0])
        
    if not ids_to_delete:
        print("No articles found to clean up.")
        session.close()
        return

    if dry_run:
        print(f"\n[DRY RUN] Would delete {len(ids_to_delete)} articles.")
        print("Run with --force to actually delete.")
    else:
        print(f"\nDeleting {len(ids_to_delete)} articles...")
        session.execute(delete(Article).where(Article.id.in_(ids_to_delete)))
        session.commit()
        print("Done.")

    session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Cleanup articles with HTML in titles')
    parser.add_argument('--force', action='store_true', help='Actually delete the articles')
    args = parser.parse_args()
    
    cleanup_html_titles(dry_run=not args.force)

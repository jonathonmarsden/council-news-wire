import sys
import os
from sqlalchemy import select

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.database import Database
from core.models import Article

def fix_cairns_urls():
    db = Database()
    session = db.get_session()
    
    print("Scanning Cairns articles...")
    
    # Find all Cairns articles
    articles = session.execute(
        select(Article).where(Article.council_id == 'cairns')
    ).scalars().all()
    
    base_pattern = "https://www.cairns.qld.gov.au/council/news-notices/media-releases/"
    double_pattern = "https://www.cairns.qld.gov.au/council/news-notices/media-releases/media-releases/"
    
    updates = 0
    duplicates = 0
    
    for article in articles:
        url = article.url
        
        # Check if it's a single path URL that needs upgrading
        if url.startswith(base_pattern) and not url.startswith(double_pattern):
            slug = url.replace(base_pattern, "")
            new_url = double_pattern + slug
            
            print(f"Found single path: {slug}")
            
            # Check if new_url already exists
            existing = session.execute(
                select(Article).where(Article.url == new_url)
            ).scalar_one_or_none()
            
            if existing:
                print(f"  ⚠️ Double path version already exists (ID: {existing.id})")
                duplicates += 1
                # If the old one was posted but the new one wasn't, we might want to mark the new one as posted?
                # But usually the new one is the one that just got scraped and maybe posted.
                
                # If the new one is NOT posted, but the old one IS, we should mark the new one as posted
                # to prevent it from being posted (if it hasn't been already).
                if article.posted_at and not existing.posted_at:
                    print(f"  ✅ Marking new version as posted (copied from old ID {article.id})")
                    existing.posted_at = article.posted_at
                    existing.posted_to_handle = 'MIGRATED'
                    updates += 1
            else:
                print(f"  🔄 Updating URL to double path")
                article.url = new_url
                updates += 1

    session.commit()
    session.close()
    
    print(f"\nSummary: {updates} updates, {duplicates} duplicates found.")

if __name__ == "__main__":
    fix_cairns_urls()

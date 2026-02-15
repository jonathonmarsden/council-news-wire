import re
import sys
from pathlib import Path
from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[2]))

from core.database import Database
from core.models import Article

def fix_warren_db():
    db = Database()
    session = db.get_session()

    rows = session.execute(
        select(Article).where(Article.council_id == 'warren-shire-council')
    ).scalars().all()
    
    print(f"Found {len(rows)} articles for Warren Shire.")
    
    updates = 0
    for row in rows:
        original_title = row.title
        if not original_title:
            continue
            
        new_title = original_title
        
        # 1. Remove date suffix (Robust method)
        # Pattern: matches date at end of string: "DD Month YYYY"
        date_pattern = r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2})$'
        match = re.search(date_pattern, new_title, re.IGNORECASE)
        if match:
            # Cut the string before the date
            new_title = new_title[:match.start()].strip()
        
        # 2. Remove prefix
        prefix_pattern = r'^(Media Release|Press Release|News Release)[:\s-]*'
        new_title = re.sub(prefix_pattern, '', new_title, flags=re.IGNORECASE).strip()
        
        if new_title != original_title:
            print(f"Fixing: '{original_title}' -> '{new_title}'")
            row.title = new_title
            updates += 1

    session.commit()
    print(f"Updated {updates} articles.")
    session.close()

if __name__ == "__main__":
    fix_warren_db()

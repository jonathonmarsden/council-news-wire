import urllib.parse
from sqlalchemy.orm import Session
from sqlalchemy import text
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from core.database import Database
from core.models import Article

def fix_non_ascii_urls():
    """
    Scans the database for URLs containing non-ASCII characters
    and updates them to their percent-encoded equivalents.
    """
    db = Database()
    print("Connecting to database...")
    
    with db.get_session() as session:
        # Find articles with non-ASCII characters in URL
        # Regex for non-ASCII: [^\x00-\x7F] (Postgres specific syntax ~ '[^[:ascii:]]' used in detection, but here we iterate)
        
        # We need to fetch all potentially bad URLs first
        # Doing a simple fetch and python check is safer than complex SQL updates for URL encoding
        
        print("Scanning for non-ASCII URLs...")
        # Fetch non-posted or recently posted items to be safe, or just all items
        # Let's fix ALL items so we don't hit this again.
        stmt = text("SELECT id, url, title FROM articles WHERE url ~ '[^[:ascii:]]'")
        results = session.execute(stmt).fetchall()
        
        print(f"Found {len(results)} articles with invalid URLs.")
        
        updated_count = 0
        
        for row in results:
            original_url = row.url
            try:
                # Encode only the non-ASCII chars, keep the rest safe
                # urllib.parse.quote handles this. 
                # safe=":/" ensures we don't break the protocol or path structure too much
                # But typically full URLs should just be quoted carefully.
                
                # If we just use quote, it might encode :// into %3A%2F%2F which is valid but maybe not what we want to store?
                # Actually, browsers usually encode the path part. 
                # Let's assume the schema/domain is fine (usually is) and the path has the junk.
                
                # Simple approach: quote the whole string but mark safe chars
                encoded_url = urllib.parse.quote(original_url, safe=":/?#=&")
                
                if encoded_url != original_url:
                    # Update DB
                    session.execute(
                        text("UPDATE articles SET url = :new_url WHERE id = :id"),
                        {"new_url": encoded_url, "id": row.id}
                    )
                    updated_count += 1
            except Exception as e:
                print(f"Failed to encode {row.id}: {e}")

        print(f"Updated {updated_count} URLs.")
        session.commit()

if __name__ == "__main__":
    fix_non_ascii_urls()

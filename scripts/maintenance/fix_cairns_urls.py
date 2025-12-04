import sqlite3
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def fix_cairns_urls():
    db_path = 'bot.db'
    if not os.path.exists(db_path):
        print("bot.db not found")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("Scanning Cairns articles...")
    
    # Find all Cairns articles
    cursor.execute("SELECT id, url, title, posted_at FROM articles WHERE council_id = 'cairns'")
    articles = cursor.fetchall()
    
    base_pattern = "https://www.cairns.qld.gov.au/council/news-notices/media-releases/"
    double_pattern = "https://www.cairns.qld.gov.au/council/news-notices/media-releases/media-releases/"
    
    updates = 0
    duplicates = 0
    
    for article in articles:
        url = article['url']
        
        # Check if it's a single path URL that needs upgrading
        if url.startswith(base_pattern) and not url.startswith(double_pattern):
            slug = url.replace(base_pattern, "")
            new_url = double_pattern + slug
            
            print(f"Found single path: {slug}")
            
            # Check if new_url already exists
            cursor.execute("SELECT id, posted_at FROM articles WHERE url = ?", (new_url,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"  ⚠️ Double path version already exists (ID: {existing['id']})")
                duplicates += 1
                # If the old one was posted but the new one wasn't, we might want to mark the new one as posted?
                # But usually the new one is the one that just got scraped and maybe posted.
                
                # If the new one is NOT posted, but the old one IS, we should mark the new one as posted
                # to prevent it from being posted (if it hasn't been already).
                if article['posted_at'] and not existing['posted_at']:
                    print(f"  ✅ Marking new version as posted (copied from old ID {article['id']})")
                    cursor.execute(
                        "UPDATE articles SET posted_at = ?, posted_to_handle = ? WHERE id = ?",
                        (article['posted_at'], 'MIGRATED', existing['id'])
                    )
                    updates += 1
            else:
                print(f"  🔄 Updating URL to double path")
                cursor.execute("UPDATE articles SET url = ? WHERE id = ?", (new_url, article['id']))
                updates += 1
                
    conn.commit()
    conn.close()
    
    print(f"\nSummary: {updates} updates, {duplicates} duplicates found.")

if __name__ == "__main__":
    fix_cairns_urls()

import sqlite3
import re
import os

def fix_warren_db():
    db_path = "bot.db"
    if not os.path.exists(db_path):
        # Try absolute path on VPS
        db_path = "/opt/council-news-bot/data/bot.db"
        
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, title FROM articles WHERE council_id = 'warren-shire-council'")
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} articles for Warren Shire.")
    
    updates = 0
    for row in rows:
        original_title = row['title']
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
            cursor.execute("UPDATE articles SET title = ? WHERE id = ?", (new_title, row['id']))
            updates += 1
            
    conn.commit()
    print(f"Updated {updates} articles.")
    conn.close()

if __name__ == "__main__":
    fix_warren_db()

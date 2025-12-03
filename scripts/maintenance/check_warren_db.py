
import sqlite3
import sys
import os

def check_warren_titles():
    db_path = "bot.db"
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Checking Warren Shire Council articles...")
    cursor.execute("""
        SELECT title, url, date 
        FROM articles 
        WHERE council_id = 'warren-shire-council' 
        ORDER BY date DESC 
        LIMIT 10
    """)
    
    rows = cursor.fetchall()
    if not rows:
        print("No articles found for Warren Shire Council.")
    
    for row in rows:
        title, url, date = row
        print(f"Date: {date}")
        print(f"Title: {title}")
        print(f"URL: {url}")
        print("-" * 40)
        
    conn.close()

if __name__ == "__main__":
    check_warren_titles()

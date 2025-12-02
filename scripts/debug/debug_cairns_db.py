import sqlite3
import os

def check_cairns_duplicates():
    db_path = 'bot.db'
    if not os.path.exists(db_path):
        print("bot.db not found")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("Checking for duplicates in DB...")
    
    # Find specific title
    title = "EOIs now open for Cairns Children's Festival 2026"
    print(f"Checking for title: {title}")
    
    details = conn.execute(
        "SELECT id, council_id, state, posted_at, url FROM articles WHERE title = ?", 
        (title,)
    ).fetchall()
    
    if not details:
        print("No articles found with that title.")
    
    for d in details:
        print(f"  ID: {d['id']} | State: {d['state']} | Posted: {d['posted_at']} | Handle: {d.get('posted_to_handle')} | URL: {d['url']}")

if __name__ == "__main__":
    check_cairns_duplicates()

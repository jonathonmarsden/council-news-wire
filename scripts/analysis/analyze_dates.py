import sqlite3
import os

DB_PATH = 'bot.db'

def analyze_dates():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check schema
    cursor.execute("PRAGMA table_info(articles)")
    columns = [info[1] for info in cursor.fetchall()]
    print(f"Columns: {columns}")

    # Count total articles
    cursor.execute("SELECT COUNT(*) FROM articles")
    total = cursor.fetchone()[0]

    # Count articles with no date
    cursor.execute("SELECT COUNT(*) FROM articles WHERE date IS NULL OR date = ''")
    no_date = cursor.fetchone()[0]

    print(f"Total Articles: {total}")
    print(f"Articles with No Date: {no_date}")

    # Group by council_id for no date
    cursor.execute("""
        SELECT council_id, COUNT(*) as count 
        FROM articles 
        WHERE date IS NULL OR date = '' 
        GROUP BY council_id 
        ORDER BY count DESC
        LIMIT 20
    """)
    
    print("\nTop Councils with Missing Dates:")
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1]}")

    conn.close()

if __name__ == "__main__":
    analyze_dates()

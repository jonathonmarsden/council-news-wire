
import sqlite3
import os

DB_PATH = '/opt/council-news-bot/data/bot.db'

def check_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check counts by state
    print("--- Articles by State ---")
    cursor.execute("SELECT state, COUNT(*) FROM articles GROUP BY state")
    for row in cursor.fetchall():
        print(f"State: {row[0]}, Count: {row[1]}")

    # Check unposted by state
    print("\n--- Unposted Articles by State ---")
    cursor.execute("SELECT state, COUNT(*) FROM articles WHERE posted_at IS NULL AND status != 'archived' GROUP BY state")
    for row in cursor.fetchall():
        print(f"State: {row[0]}, Count: {row[1]}")

    conn.close()

if __name__ == "__main__":
    check_db()

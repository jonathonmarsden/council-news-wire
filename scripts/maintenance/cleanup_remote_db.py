import sys
import os
import sqlite3

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

try:
    from core.config import DB_PATH
except ImportError:
    # Fallback if config can't be imported easily without proper context
    DB_PATH = 'data/bot.db'

def cleanup_malformed_posts():
    print(f"Connecting to {DB_PATH} ...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Delete articles from the future (Year > 2027)
        print("Scanning for future dates...")
        cursor.execute("DELETE FROM articles WHERE date > '2027-01-01'")
        if cursor.rowcount > 0:
            print(f"Deleted {cursor.rowcount} future rows.")

        # 2. Deletes titles that are just "Posted ..."
        print("Scanning for 'Posted ...' titles...")
        cursor.execute("SELECT id, council_id, title FROM articles WHERE title LIKE 'Posted %'")
        posted_rows = cursor.fetchall()
        count = 0
        for row in posted_rows:
            if any(char.isdigit() for char in row[2]):
                print(f"  - Deleting: {row}")
                cursor.execute("DELETE FROM articles WHERE id = ?", (row[0],))
                count += 1
        print(f"Deleted {count} 'Posted ...' rows.")

        # 3. Delete copyright titles
        print("Scanning for copyright titles...")
        cursor.execute("DELETE FROM articles WHERE title LIKE '©%' OR title LIKE '&copy;%'")
        if cursor.rowcount > 0:
            print(f"Deleted {cursor.rowcount} copyright rows.")

        # 4. Delete 'Found Cat' / 'ATO image'
        print("Scanning for garbage phrases...")
        garbage = ['Found Cat', 'Found Dog', 'ATO image', 'Array', 'No Title']
        for g in garbage:
            cursor.execute("DELETE FROM articles WHERE title = ?", (g,))
            if cursor.rowcount > 0:
                print(f"Deleted {cursor.rowcount} rows with title '{g}'")

        conn.commit()
        print("Cleanup complete.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    cleanup_malformed_posts()
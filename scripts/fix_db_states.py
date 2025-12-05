
import sqlite3
import os

DB_PATH = 'bot.db'

def fix_state_case():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Updating state codes to uppercase...")
    cursor.execute("UPDATE articles SET state = UPPER(state)")
    print(f"Updated {cursor.rowcount} rows.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    fix_state_case()

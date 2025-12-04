
import sqlite3
import os
from datetime import datetime, timedelta
import json

def get_db_connection():
    # Prefer absolute path to data volume
    db_path = "/opt/council-news-bot/data/bot.db"
    if not os.path.exists(db_path):
        # Fallback to local
        db_path = "bot.db"
    
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def generate_report():
    conn = get_db_connection()
    if not conn:
        print("Error: Database not found.")
        return

    cursor = conn.cursor()
    now = datetime.now()
    one_day_ago = now - timedelta(days=1)
    seven_days_ago = now - timedelta(days=7)

    report = {
        "generated_at": now.isoformat(),
        "stats": {},
        "councils": {},
        "recent_posts": []
    }

    # 1. Overall Stats (Last 24h)
    cursor.execute("""
        SELECT state, COUNT(*) as count 
        FROM articles 
        WHERE first_seen_at > ? 
        GROUP BY state
    """, (one_day_ago,))
    
    report["stats"]["collected_24h"] = {row['state']: row['count'] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT state, COUNT(*) as count 
        FROM articles 
        WHERE posted_at > ? 
        GROUP BY state
    """, (one_day_ago,))
    
    report["stats"]["posted_24h"] = {row['state']: row['count'] for row in cursor.fetchall()}

    # 2. Specific Council Checks
    target_councils = [
        'warren-shire-council', # NSW - Fixed title parsing
        'cairns',               # QLD - Duplicate issues
        'glamorgan-spring-bay', # TAS - Fixed RSS
        'break-o-day',          # TAS - Fixed RSS
        'brighton',             # TAS - Fixed RSS
        'circular-head',        # TAS - Android User-Agent fix
        'kingborough',          # TAS
        'huon-valley'           # TAS
    ]
    
    print("\n=== Target Council Status (Last 7 Days) ===")
    for council_id in target_councils:
        cursor.execute("""
            SELECT COUNT(*) as count, MAX(first_seen_at) as last_seen
            FROM articles 
            WHERE council_id = ? AND first_seen_at > ?
        """, (council_id, seven_days_ago))
        row = cursor.fetchone()
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM articles 
            WHERE council_id = ? AND posted_at > ?
        """, (council_id, one_day_ago))
        posted_24h = cursor.fetchone()['count']
        
        print(f"{council_id}: {row['count']} collected (Last seen: {row['last_seen']}), {posted_24h} posted in last 24h")

    # 3. Warren Specific Check (Title Quality)
    print("\n=== Warren Shire Recent Titles ===")
    cursor.execute("""
        SELECT title, url, posted_at 
        FROM articles 
        WHERE council_id = 'warren-shire-council' 
        ORDER BY id DESC LIMIT 5
    """)
    for row in cursor.fetchall():
        status = "Posted" if row['posted_at'] else "Pending"
        print(f"[{status}] {row['title']}")

    # 4. Total Councils Active
    cursor.execute("""
        SELECT COUNT(DISTINCT council_id) as count 
        FROM articles 
        WHERE first_seen_at > ?
    """, (seven_days_ago,))
    active_councils = cursor.fetchone()['count']
    print(f"\nTotal Active Councils (7d): {active_councils}")

    conn.close()

if __name__ == "__main__":
    generate_report()

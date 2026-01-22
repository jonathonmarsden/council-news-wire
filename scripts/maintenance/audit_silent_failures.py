import sqlite3
import datetime
import os

DB_PATH = 'data/bot.db'
if not os.path.exists(DB_PATH):
    # Fallback for local testing if running from root
    DB_PATH = 'bot.db'

def main():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    print("=== Zero Yield Audit ===")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. Identify "Active" scrapers that have found 0 articles in last 5 runs
    query = """
    WITH RecentRuns AS (
        SELECT 
            council_id, 
            status, 
            articles_found,
            ROW_NUMBER() OVER (PARTITION BY council_id ORDER BY run_at DESC) as rn
        FROM scraper_stats
        WHERE run_at > datetime('now', '-3 days')
    )
    SELECT council_id
    FROM RecentRuns
    WHERE rn <= 5
    GROUP BY council_id
    HAVING COUNT(*) = 5 AND SUM(articles_found) = 0
    """
    
    c.execute(query)
    zombies = [r[0] for r in c.fetchall()]
    
    print(f"Found {len(zombies)} 'Zombie' scrapers (Active but 0 returns in last 5 runs):")
    for z in zombies:
        print(f" - {z}")
        
    # 2. Identify "Silent Errors" (status='error' but no disable)
    c.execute("""
        SELECT council_id, COUNT(*) as failures 
        FROM scraper_stats 
        WHERE status='error' AND run_at > datetime('now', '-24 hours')
        GROUP BY council_id
        HAVING failures > 0
    """)
    errors = c.fetchall()
    print(f"\nFound {len(errors)} scrapers with recent errors:")
    for council_id, count in errors:
        print(f" - {council_id}: {count} errors in 24h")

    conn.close()

if __name__ == "__main__":
    main()

import os
import sys
from sqlalchemy import text
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from core.database import Database

def main():
    print("=== Zero Yield Audit ===")
    
    try:
        db = Database()
        session = db.get_session()
    except Exception as e:
        print(f"Error: Could not connect to database: {e}")
        return

    # 1. Identify "Active" scrapers that have found 0 articles in last 5 runs
    query = text("""
    WITH RecentRuns AS (
        SELECT 
            council_id, 
            status, 
            articles_found,
            ROW_NUMBER() OVER (PARTITION BY council_id ORDER BY run_at DESC) as rn
        FROM scraper_stats
        WHERE run_at > now() - interval '7 days'
    )
    SELECT council_id
    FROM RecentRuns
    WHERE rn <= 5
    GROUP BY council_id
    HAVING COUNT(*) >= 5 AND SUM(articles_found) = 0
    """)
    
    try:
        result = session.execute(query)
        zombies = [row[0] for row in result]
        
        if zombies:
            print(f"Warning: Found {len(zombies)} 'Zombie' scrapers (Active but 0 returns in last 5 runs):")
            for z in zombies:
                print(f" - {z}")
        else:
            print("No Zombie scrapers found.")
            
    except Exception as e:
        print(f"Query failed: {e}")

    # 2. Identify "Silent Errors" (status='error' but no disable)
    # Simplified for now
    
    session.close()

if __name__ == "__main__":
    main()

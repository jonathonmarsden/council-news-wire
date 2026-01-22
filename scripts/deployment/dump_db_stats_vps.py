import sqlite3
import sys

# Run this on VPS via ssh
# python3 -c "..."

def get_stats():
    conn = sqlite3.connect('/opt/council-news-bot/data/bot.db')
    c = conn.cursor()
    # Get total count and last seen date for each council
    # We join with scraper_stats to get more recent activity or just use articles?
    # Actually, articles table has 'first_seen_at'.
    # But checking scraper_stats is better for 'last run'.
    # The existing report script uses `remote_db_stats.csv` which seemed to come from article counts.
    # Let's try to match the expected format: council_id|count|last_seen|state
    
    query = """
    SELECT 
        council_id,
        COUNT(*) as article_count,
        MAX(first_seen_at) as last_seen,
        state
    FROM articles 
    GROUP BY council_id
    ORDER BY state, council_id
    """
    
    c.execute(query)
    for row in c.fetchall():
        # Handle None
        cid = row[0]
        cnt = row[1]
        last = row[2] if row[2] else "1970-01-01 00:00:00"
        st = row[3]
        print(f"{cid}|{cnt}|{last}|{st}")
        
    conn.close()

if __name__ == "__main__":
    get_stats()

import json
import os
import sqlite3
import glob
from datetime import datetime, timedelta

def get_db_connection():
    # Prefer absolute path to data volume on VPS
    db_path = "/opt/council-news-bot/data/bot.db"
    if not os.path.exists(db_path):
        # Fallback to local
        db_path = "bot.db"
    
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def load_all_councils():
    councils = {}
    
    # Check states directory
    state_files = glob.glob("states/*/councils.json")
    for fpath in state_files:
        state = os.path.basename(os.path.dirname(fpath))
        try:
            with open(fpath, 'r') as f:
                data = json.load(f)
                for c in data.get('councils', []):
                    if c.get('enabled', True):
                        c['state'] = state
                        councils[c['id']] = c
        except Exception as e:
            print(f"Error loading {fpath}: {e}")

    # Also check config/councils.json if it exists and isn't covered
    # (Assuming states/ is the source of truth, but let's check)
    
    return councils

def main():
    conn = get_db_connection()
    if not conn:
        print("Error: Database not found.")
        return

    councils = load_all_councils()
    print(f"Loaded {len(councils)} enabled councils configuration.")
    
    cursor = conn.cursor()
    
    # Get last seen date for all councils
    cursor.execute("""
        SELECT council_id, MAX(first_seen_at) as last_seen, COUNT(*) as total_count
        FROM articles 
        GROUP BY council_id
    """)
    
    db_stats = {row['council_id']: row for row in cursor.fetchall()}
    
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    
    healthy = []
    quiet = []
    silent = []
    never = []
    
    for cid, config in councils.items():
        stat = db_stats.get(cid)
        
        if not stat:
            never.append(config)
            continue
            
        last_seen_str = stat['last_seen']
        if not last_seen_str:
            never.append(config)
            continue
            
        try:
            # Handle potential different date formats if necessary, but usually ISO in DB
            last_seen = datetime.fromisoformat(last_seen_str)
        except ValueError:
            # Fallback for non-iso
            last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S")

        info = {
            'id': cid,
            'name': config['name'],
            'state': config.get('state', 'Unknown'),
            'last_seen': last_seen_str,
            'total': stat['total_count']
        }
        
        if last_seen > seven_days_ago:
            healthy.append(info)
        elif last_seen > thirty_days_ago:
            quiet.append(info)
        else:
            silent.append(info)

    print(f"\n=== Health Summary ===")
    print(f"Total Enabled: {len(councils)}")
    print(f"✅ Healthy (<7d): {len(healthy)}")
    print(f"⚠️ Quiet (7-30d): {len(quiet)}")
    print(f"❌ Silent (>30d): {len(silent)}")
    print(f"💀 Never Seen:    {len(never)}")
    
    print(f"\n=== 💀 Never Seen Councils ({len(never)}) ===")
    for c in sorted(never, key=lambda x: x.get('state', '')):
        print(f"[{c.get('state')}] {c['id']} ({c['name']})")

    print(f"\n=== ❌ Silent Councils (>30d) ({len(silent)}) ===")
    for c in sorted(silent, key=lambda x: x['last_seen']):
        print(f"[{c['state']}] {c['id']}: Last seen {c['last_seen']} (Total: {c['total']})")

    print(f"\n=== ⚠️ Quiet Councils (7-30d) ({len(quiet)}) ===")
    for c in sorted(quiet, key=lambda x: x['last_seen']):
        print(f"[{c['state']}] {c['id']}: Last seen {c['last_seen']} (Total: {c['total']})")

if __name__ == "__main__":
    main()

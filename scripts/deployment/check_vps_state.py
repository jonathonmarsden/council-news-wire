
import pty
import os
import sys
import time

# Add current directory to path to allow importing deploy_secrets
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

def read(fd):
    return os.read(fd, 1024)

def run_remote_command(command):
    ssh_cmd = ["ssh", "-o", "PreferredAuthentications=password", "-o", "PubkeyAuthentication=no", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", f"{USER}@{HOST}", command]
    
    print(f"Running: {command}")
    
    pid, fd = pty.fork()
    
    if pid == 0:
        os.execvp(ssh_cmd[0], ssh_cmd)
    else:
        try:
            while True:
                try:
                    output = read(fd).decode(errors='ignore')
                    if not output:
                        break
                    sys.stdout.write(output)
                    sys.stdout.flush()
                    
                    if "password:" in output.lower():
                        time.sleep(0.5)
                        os.write(fd, (PASS + "\n").encode())
                        
                except OSError:
                    break
        except Exception as e:
            print(f"Error: {e}")
        finally:
            os.close(fd)

def main():
    print("=== Checking VPS State ===")
    
    # 1. Check Time
    print("\n--- VPS Date/Time ---")
    run_remote_command("date")
    
    # 2. Upload fixed DB script
    print("\n--- Uploading DB Script ---")
    # We can't easily use scp with pty/password here without a library or system call.
    # Instead, let's just write the script content directly via echo since it's small.
    # Or better, just run the python code as a one-liner string.
    
    db_script = """
import sqlite3
import os
DB_PATH = '/opt/council-news-bot/data/bot.db'
if not os.path.exists(DB_PATH):
    print(f'Database not found at {DB_PATH}')
else:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    print('--- Unposted Articles ---')
    c.execute("SELECT state, COUNT(*) FROM articles WHERE posted_at IS NULL AND status != 'archived' GROUP BY state")
    for r in c.fetchall(): print(f'{r[0]}: {r[1]}')
    print('--- Recent Scraper Runs for Missing States ---')
    states = ['NSW', 'ACT', 'SA', 'WA', 'NT']
    for state in states:
        print(f'Checking {state}...')
        # Get councils for this state from articles table to cross reference
        c.execute("SELECT DISTINCT council_id FROM articles WHERE state=?", (state,))
        councils = [r[0] for r in c.fetchall()]
        
        if not councils:
            print(f"  No councils found in DB for {state}")
            continue
            
        # Check stats for these councils
        placeholders = ','.join(['?'] * len(councils))
        query = f"SELECT council_id, articles_found, status, run_at FROM scraper_stats WHERE council_id IN ({placeholders}) AND run_at > datetime('now', '-1 day') ORDER BY run_at DESC LIMIT 5"
        c.execute(query, councils)
        rows = c.fetchall()
        if not rows:
            print("  No scraper runs recorded in last 24h")
        for r in rows:
            print(f"  {r[0]}: Found {r[1]} ({r[2]}) at {r[3]}")

    conn.close()
"""
    # Escape quotes for bash
    db_script_escaped = db_script.replace('"', '\\"')
    
    run_remote_command(f'python3 -c "{db_script_escaped}"')
    
    print("\n=== Check Complete ===")

if __name__ == "__main__":
    main()

import json
import os
import re
import glob
from datetime import datetime, timedelta
import sys

# Add deployment dir to path for secrets
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../deployment"))
try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    try:
        sys.path.append(os.path.join(os.getcwd(), "deployment"))
        from deploy_secrets import HOST, USER, PASS
    except ImportError:
        print("Error: deploy_secrets.py not found.")
        sys.exit(1)

import pty

def read(fd):
    return os.read(fd, 1024)

def run_command_with_pty(command, password):
    # print(f"Running: {command}")
    pid, fd = pty.fork()
    if pid == 0:
        os.execv("/bin/sh", ["/bin/sh", "-c", command])
    else:
        output_buffer = b""
        while True:
            try:
                data = read(fd)
                if not data:
                    break
                output_buffer += data
                if b"password:" in data.lower():
                    os.write(fd, (password + "\n").encode())
            except OSError:
                break
        
        _, status = os.waitpid(pid, 0)
        return output_buffer.decode(errors='ignore')

def get_db_connection():
    # Prefer absolute path to data volume on VPS (if running there)
    # But this script runs locally and connects to remote DB? 
    # No, we will just use the logs for scraper health.
    # For DB stats, we can run a quick query on remote.
    return None

def load_council_map():
    """Load all councils and return name->id and id->config mapping."""
    name_to_id = {}
    id_to_config = {}
    
    state_files = glob.glob("states/*/councils.json")
    for fpath in state_files:
        state = os.path.basename(os.path.dirname(fpath))
        try:
            with open(fpath, 'r') as f:
                data = json.load(f)
                for c in data.get('councils', []):
                    if c.get('enabled', True):
                        c['state'] = state
                        name_to_id[c['name']] = c['id']
                        id_to_config[c['id']] = c
        except Exception as e:
            print(f"Error loading {fpath}: {e}")
            
    return name_to_id, id_to_config

def get_remote_logs():
    print("Fetching logs from VPS (this may take a moment)...")
    # Fetch last 20000 lines to ensure we cover a full run
    cmd = f"ssh {USER}@{HOST} 'docker logs council_news_bot --tail 20000'"
    return run_command_with_pty(cmd, PASS)

def get_remote_db_stats():
    print("Fetching DB stats from local dump file...")
    # Read from local dump file
    dump_file = "scripts/maintenance/db_stats_dump.txt"
    if not os.path.exists(dump_file):
        print("Error: Dump file not found.")
        return {}
        
    with open(dump_file, 'r') as f:
        output = f.read()
    
    stats = {}
    for line in output.splitlines():
        if "|" in line:
            parts = line.split("|")
            if len(parts) >= 2:
                cid = parts[0].strip()
                last_seen = parts[1].strip()
                stats[cid] = last_seen
    return stats

def parse_logs(log_content, name_to_id):
    scraper_health = {} # id -> {'status': 'ok'|'error'|'empty', 'count': 0, 'msg': ''}
    
    # Regex for "  Name: Found N articles"
    found_pattern = re.compile(r"\s+(.+?): Found (\d+) articles")
    # Regex for "  Error scraping Name: ..."
    error_pattern = re.compile(r"\s+Error scraping (.+?): (.+)")
    
    lines = log_content.splitlines()
    for line in lines:
        # Check Success
        m_found = found_pattern.search(line)
        if m_found:
            name = m_found.group(1).strip()
            count = int(m_found.group(2))
            cid = name_to_id.get(name)
            if cid:
                status = 'ok' if count > 0 else 'empty'
                scraper_health[cid] = {'status': status, 'count': count, 'msg': 'Success'}
            continue
            
        # Check Error
        m_error = error_pattern.search(line)
        if m_error:
            name = m_error.group(1).strip()
            msg = m_error.group(2).strip()
            cid = name_to_id.get(name)
            if cid:
                scraper_health[cid] = {'status': 'error', 'count': 0, 'msg': msg}
            continue
            
    return scraper_health

def main():
    name_to_id, id_to_config = load_council_map()
    print(f"Loaded {len(id_to_config)} enabled councils.")
    
    logs = get_remote_logs()
    db_stats = get_remote_db_stats()
    
    scraper_health = parse_logs(logs, name_to_id)
    
    # Analysis
    
    # 1. Freshness (DB Based)
    fresh_count = 0
    stale_count = 0
    never_count = 0
    
    now = datetime.now()
    thirty_days_ago = now - timedelta(days=30)
    
    for cid, config in id_to_config.items():
        last_seen_str = db_stats.get(cid)
        if last_seen_str:
            try:
                # Handle potential formats
                last_seen = datetime.fromisoformat(last_seen_str)
            except ValueError:
                try:
                    last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S")
                except:
                    last_seen = datetime.min
            
            if last_seen > thirty_days_ago:
                fresh_count += 1
                config['freshness'] = 'fresh'
            else:
                stale_count += 1
                config['freshness'] = 'stale'
        else:
            never_count += 1
            config['freshness'] = 'never'

    # 2. Scraper Health (Log Based)
    working_count = 0 # Found > 0
    empty_count = 0   # Found 0
    error_count = 0   # Error
    unknown_count = 0 # No log
    
    for cid, config in id_to_config.items():
        health = scraper_health.get(cid)
        if health:
            config['scraper_status'] = health['status']
            config['scraper_count'] = health['count']
            config['scraper_msg'] = health['msg']
            
            if health['status'] == 'ok':
                working_count += 1
            elif health['status'] == 'empty':
                empty_count += 1
            else:
                error_count += 1
        else:
            config['scraper_status'] = 'unknown'
            config['scraper_count'] = 0
            config['scraper_msg'] = 'No log entry found'
            unknown_count += 1

    # Generate Report
    print("\n" + "="*50)
    print("       DEEP HEALTH ANALYSIS REPORT")
    print("="*50)
    
    print(f"\nSECTION 1: FRESHNESS (Database - Last 30 Days)")
    print(f"Total Enabled: {len(id_to_config)}")
    print(f"✅ Fresh (Posted <30d): {fresh_count}")
    print(f"⚠️ Stale (Posted >30d): {stale_count}")
    print(f"❌ Never Seen:          {never_count}")
    
    print(f"\nSECTION 2: SCRAPER HEALTH (Logs - Last Run)")
    print(f"✅ Working (Found > 0): {working_count}")
    print(f"⚠️ Empty (Found 0):     {empty_count}")
    print(f"❌ Error:               {error_count}")
    print(f"❓ Unknown (No Logs):   {unknown_count}")
    
    print(f"\nSECTION 3: THE 'WORKING BUT OLD' COHORT")
    print("These scrapers are finding articles, but they are not being saved to DB (likely old).")
    print("This confirms the scraper IS working, just no *new* news.")
    
    working_but_never_seen = []
    for cid, config in id_to_config.items():
        if config['freshness'] == 'never' and config['scraper_status'] == 'ok':
            working_but_never_seen.append(config)
            
    print(f"Count: {len(working_but_never_seen)}")
    if working_but_never_seen:
        print("Sample (First 10):")
        for c in working_but_never_seen[:10]:
            print(f"- {c['id']} (Found {c['scraper_count']} articles)")

    print(f"\nSECTION 4: BROKEN SCRAPERS (Errors)")
    broken = [c for c in id_to_config.values() if c['scraper_status'] == 'error']
    print(f"Count: {len(broken)}")
    for c in broken:
        print(f"- {c['id']}: {c['scraper_msg']}")

if __name__ == "__main__":
    main()

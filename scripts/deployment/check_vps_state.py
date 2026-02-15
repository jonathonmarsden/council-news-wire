
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
    
    print("\n--- Database Snapshot (Postgres) ---")
    db_command = """
cd /opt/council-news-bot && docker compose exec -T db psql -U councilbot -d council_news <<'SQL'
\pset pager off
\echo '--- Unposted Articles ---'
select state, count(*) as unposted
from articles
where posted_at is null and status != 'archived'
group by state
order by state;

\echo '--- Recent Scraper Runs (Last 24h) ---'
select council_id, articles_found, status, run_at
from scraper_stats
where run_at > now() - interval '1 day'
order by run_at desc
limit 10;
SQL
"""
    run_remote_command(db_command)
    
    print("\n=== Check Complete ===")

if __name__ == "__main__":
    main()

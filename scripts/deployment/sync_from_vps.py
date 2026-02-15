#!/usr/bin/env python3
"""
Sync database and/or code changes FROM the VPS back to local.

Usage:
    python scripts/deployment/sync_from_vps.py           # Sync database (pg_dump)
    python scripts/deployment/sync_from_vps.py --code    # Also pull any code changes from VPS
    python scripts/deployment/sync_from_vps.py --dry-run # Show what would be synced
"""

import pty
import os
import sys
import time
import argparse
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from deploy_secrets import HOST, USER, PASS
except ImportError:
    print("Error: deploy_secrets.py not found.")
    sys.exit(1)

TARGET_DIR = "/opt/council-news-bot"
LOCAL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_with_password(command: str) -> bool:
    """Run a command, auto-entering password when prompted."""
    pid, fd = pty.fork()
    
    if pid == 0:
        os.execv("/bin/bash", ["/bin/bash", "-c", command])
    else:
        try:
            while True:
                try:
                    output = os.read(fd, 1024).decode(errors='ignore')
                    if not output:
                        break
                    sys.stdout.write(output)
                    sys.stdout.flush()
                    
                    if "password:" in output.lower():
                        time.sleep(0.3)
                        os.write(fd, (PASS + "\n").encode())
                    if "continue connecting" in output.lower():
                        time.sleep(0.3)
                        os.write(fd, b"yes\n")
                except OSError:
                    break
        except Exception as e:
            print(f"Error: {e}")
            return False
        finally:
            os.close(fd)
            _, status = os.waitpid(pid, 0)
            return status == 0
    return True


def ensure_dump_dir() -> str:
    """Ensure a local directory exists for DB dumps."""
    dump_dir = os.path.join(LOCAL_DIR, "db_dumps")
    os.makedirs(dump_dir, exist_ok=True)
    return dump_dir


def sync_database(dry_run: bool = False):
    """Pull the database from VPS to local."""
    print("\n=== Syncing Database from VPS ===")
    
    ssh_opts = "-o PreferredAuthentications=password -o PubkeyAuthentication=no -o StrictHostKeyChecking=no"
    
    if dry_run:
        cmd = f'ssh {ssh_opts} {USER}@{HOST} "cd {TARGET_DIR} && docker compose exec -T db psql -U councilbot -d council_news -c \\\"select count(*) as total_articles from articles;\\\""'
        print("Would sync: Postgres pg_dump → local db_dumps/")
        run_with_password(cmd)
        return

    dump_dir = ensure_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_dump = os.path.join(dump_dir, f"council_news_{timestamp}.sql")

    cmd = (
        f'ssh {ssh_opts} {USER}@{HOST} "cd {TARGET_DIR} && '
        f'docker compose exec -T db pg_dump -U councilbot council_news" '
        f'> {local_dump}'
    )
    print(f"Dumping Postgres to {local_dump}...")
    run_with_password(cmd)

    print("✓ Database dump synced from VPS")


def sync_code(dry_run: bool = False):
    """Pull any code changes from VPS (use with caution)."""
    print("\n=== Syncing Code Changes from VPS ===")
    print("⚠️  Warning: This will overwrite local changes with VPS versions")
    
    ssh_opts = "-o PreferredAuthentications=password -o PubkeyAuthentication=no -o StrictHostKeyChecking=no"
    
    if dry_run:
        # Show what's different
        cmd = f'ssh {ssh_opts} {USER}@{HOST} "cd {TARGET_DIR} && find . -name \"*.py\" -mtime -1 -type f 2>/dev/null | head -20"'
        print("Recently modified Python files on VPS:")
        run_with_password(cmd)
        return
    
    # Pull code changes (excluding stuff we don't want)
    cmd = f'''rsync -avz --progress -e "ssh {ssh_opts}" \
        --exclude 'venv' \
        --exclude '.git' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.DS_Store' \
        --exclude 'data' \
        --exclude '*.db' \
        --exclude '*.db-*' \
        --exclude 'scheduler.log' \
        --exclude '.env' \
        --exclude 'backups' \
        {USER}@{HOST}:{TARGET_DIR}/ {LOCAL_DIR}/'''
    
    run_with_password(cmd)
    print("✓ Code synced from VPS")
    print("\n⚠️  Remember to review changes with 'git diff' before committing!")


def show_vps_status():
    """Show current VPS database stats."""
    print("\n=== VPS Database Status ===")
    ssh_opts = "-o PreferredAuthentications=password -o PubkeyAuthentication=no -o StrictHostKeyChecking=no"

    cmd = f'''ssh {ssh_opts} {USER}@{HOST} "cd {TARGET_DIR} && \\
        echo '--- Database size ---' && \\
        docker compose exec -T db psql -U councilbot -d council_news -c \\\"select pg_size_pretty(pg_database_size('council_news'));\\\" && \\
        echo '' && \\
        echo '--- Article counts ---' && \\
        docker compose exec -T db psql -U councilbot -d council_news -c \\\"select state, count(*) as count from articles group by state order by count desc;\\\" && \\
        echo '' && \\
        echo '--- Recent articles ---' && \\
        docker compose exec -T db psql -U councilbot -d council_news -c \\\"select first_seen_at, council_id, left(title,50) from articles order by first_seen_at desc limit 5;\\\""'''
    
    run_with_password(cmd)


def main():
    parser = argparse.ArgumentParser(description="Sync from VPS to local")
    parser.add_argument("--code", action="store_true", help="Also sync code changes (use with caution)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without doing it")
    parser.add_argument("--status", action="store_true", help="Just show VPS database status")
    args = parser.parse_args()
    
    if args.status:
        show_vps_status()
        return
    
    sync_database(dry_run=args.dry_run)
    
    if args.code:
        if not args.dry_run:
            response = input("\nPull code changes from VPS? This may overwrite local changes. [y/N] ")
            if response.lower() != 'y':
                print("Skipping code sync.")
                return
        sync_code(dry_run=args.dry_run)
    
    if not args.dry_run:
        print("\n=== Sync Complete ===")
        print("Database: VPS → Local ✓")
        if args.code:
            print("Code: VPS → Local ✓ (review with 'git diff')")


if __name__ == "__main__":
    main()

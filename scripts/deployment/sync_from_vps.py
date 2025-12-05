#!/usr/bin/env python3
"""
Sync database and/or code changes FROM the VPS back to local.

Usage:
    python scripts/deployment/sync_from_vps.py          # Sync database only (safe default)
    python scripts/deployment/sync_from_vps.py --code   # Also pull any code changes from VPS
    python scripts/deployment/sync_from_vps.py --dry-run # Show what would be synced
"""

import pty
import os
import sys
import time
import argparse
import shutil
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


def backup_local_db():
    """Create a backup of the local database before overwriting."""
    local_db = os.path.join(LOCAL_DIR, "bot.db")
    if os.path.exists(local_db):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(LOCAL_DIR, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f"bot_local_{timestamp}.db")
        shutil.copy2(local_db, backup_path)
        print(f"✓ Backed up local database to: backups/bot_local_{timestamp}.db")
        return backup_path
    return None


def sync_database(dry_run: bool = False):
    """Pull the database from VPS to local."""
    print("\n=== Syncing Database from VPS ===")
    
    ssh_opts = "-o PreferredAuthentications=password -o PubkeyAuthentication=no -o StrictHostKeyChecking=no"
    
    if dry_run:
        # Just show remote DB info
        cmd = f'ssh {ssh_opts} {USER}@{HOST} "ls -lh {TARGET_DIR}/bot.db* 2>/dev/null || echo No database found"'
        print(f"Would sync: {TARGET_DIR}/bot.db → {LOCAL_DIR}/bot.db")
        run_with_password(cmd)
        return
    
    # Backup local first
    backup_local_db()
    
    # Copy database files (including WAL if present)
    for db_file in ["bot.db", "bot.db-shm", "bot.db-wal"]:
        remote_path = f"{TARGET_DIR}/{db_file}"
        local_path = os.path.join(LOCAL_DIR, db_file)
        
        cmd = f'scp {ssh_opts} {USER}@{HOST}:{remote_path} {local_path}'
        print(f"Pulling {db_file}...")
        run_with_password(cmd)
    
    print("✓ Database synced from VPS")


def sync_code(dry_run: bool = False):
    """Pull any code changes from VPS (use with caution)."""
    print("\n=== Syncing Code Changes from VPS ===")
    print("⚠️  Warning: This will overwrite local changes with VPS versions")
    
    ssh_opts = "-o PreferredAuthentications=password -o PubkeyAuthentication=no -o StrictHostKeyChecking=no"
    
    if dry_run:
        # Show what's different
        cmd = f'ssh {ssh_opts} {USER}@{HOST} "cd {TARGET_DIR} && find . -name \"*.py\" -newer bot.db -type f 2>/dev/null | head -20"'
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
        ls -lh bot.db 2>/dev/null && \\
        echo '' && \\
        echo '--- Article counts ---' && \\
        sqlite3 bot.db 'SELECT state, COUNT(*) as count FROM articles GROUP BY state ORDER BY count DESC;' 2>/dev/null && \\
        echo '' && \\
        echo '--- Recent articles ---' && \\
        sqlite3 bot.db 'SELECT datetime(scraped_at) as scraped, council, substr(title,1,50) FROM articles ORDER BY scraped_at DESC LIMIT 5;' 2>/dev/null"'''
    
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

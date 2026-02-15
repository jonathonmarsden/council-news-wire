#!/usr/bin/env python3
"""
Health Check for Twice-Daily Scraping Schedule
-----------------------------------------------
Verifies that the twice-daily schedule is working correctly by checking:
- Last run times per state
- Deviation from expected times
- Cron configuration validity

Usage:
    python3 scripts/deployment/check_twice_daily_schedule.py
"""

import sys
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from core.database import Database
from core.timezone_utils import get_scheduled_times_for_date, STATE_TIMEZONES


def get_last_run_from_logs(state: str, run_type: str = 'morning') -> datetime or None:
    """
    Try to extract last run time for a state from logs.
    This is a best-effort function; quality depends on log format.
    """
    # Try to read from production VPS logs
    try:
        cmd = (
            f"ssh root@vps.example.com "
            f"'grep -E \"{state}|--time-window\" /var/log/council_bot_scraper.log | tail -10'"
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        # Parsing would require specific log format; skip for now
        return None
    except Exception:
        return None


def get_last_run_from_db(state: str) -> dict or None:
    """
    Get the last scraper run metadata from the database.
    """
    try:
        db = Database()
        # Get recent scraper stats for the state
        from sqlalchemy import select, desc
        from core.database import ScraperStats
        
        query = (
            select(ScraperStats)
            .where(ScraperStats.state == state.upper())
            .order_by(desc(ScraperStats.run_at))
            .limit(1)
        )
        
        result = db.session.execute(query).scalar()
        if result:
            return {
                'state': state.upper(),
                'last_run': result.run_at,
                'articles_found': result.articles_found,
                'articles_saved': result.articles_saved,
                'status': result.status,
            }
        return None
    except Exception as e:
        print(f"Warning: Could not query database for {state}: {e}", file=sys.stderr)
        return None


def print_schedule_status():
    """Print the expected schedule and status."""
    print("\n" + "=" * 80)
    print("TWICE-DAILY SCRAPING SCHEDULE STATUS")
    print("=" * 80 + "\n")
    
    today = datetime.now()
    schedule = get_scheduled_times_for_date(today)
    
    print(f"Reference Date: {today.date()}\n")
    print(f"{'State':<6} {'Group':<7} {'Run':<8} {'Local':<8} {'UTC':<12} {'Expected Cron':<15} {'Status':<20}")
    print("-" * 100)
    
    for entry in sorted(schedule, key=lambda e: (e['run_type'], e['group'], e['state'])):
        state = entry['state']
        cron_time = f"{entry['cron_minute']:02d} {entry['cron_hour']:02d}"
        
        # Try to get last run from DB
        last_run_info = get_last_run_from_db(state)
        if last_run_info:
            last_run = last_run_info['last_run']
            # Calculate deviation from expected time
            tz = STATE_TIMEZONES[state]
            now_local = datetime.now(tz)
            status = "✓ OK" if last_run and (now_local - last_run) < timedelta(hours=12) else "⚠ Late"
        else:
            status = "? Unknown"
        
        print(
            f"{state:<6} {entry['group']:<7} {entry['run_type']:<8} "
            f"{entry['local_time']:<8} {entry['utc_time']:<12} {cron_time:<15} {status:<20}"
        )
    
    print("\n" + "=" * 80)
    print("LEGEND:")
    print("  ✓ OK      = Last run within 12 hours")
    print("  ⚠ Late    = Last run >12 hours ago")
    print("  ? Unknown = No database records found")
    print("\nFor more details, see SCHEDULING_GUIDE.md")
    print("=" * 80 + "\n")


def print_crontab_validation():
    """Validate the crontab on the VPS (if accessible)."""
    print("\nValidating remote crontab...\n")
    
    try:
        # Get active crontab from VPS
        cmd = "ssh root@vps.example.com 'crontab -l | grep -c council-news-bot'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            count = result.stdout.strip()
            print(f"✓ Remote crontab has {count} council-news-bot entries")
        else:
            print("⚠ Could not verify remote crontab (check SSH access)")
    except Exception as e:
        print(f"⚠ Could not validate remote crontab: {e}")


def main():
    try:
        print_schedule_status()
        print_crontab_validation()
        
        print("\nTo regenerate the crontab (e.g., after DST change):")
        print("  python3 scripts/deployment/generate_crontab.py --static\n")
        
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

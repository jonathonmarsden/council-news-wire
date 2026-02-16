#!/usr/bin/env python3
"""
Generate Crontab Entries for Twice-Daily Scraping
---------------------------------------------------
Generates cron lines for 06:00 and 18:00 local scraping across all 8 Australian states.
Accounts for time zone differences and DST transitions.

Usage:
    python3 scripts/deployment/generate_crontab.py [--date YYYY-MM-DD]

Output:
    Generates a complete crontab configuration ready to deploy to VPS.
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from core.timezone_utils import (
    get_scheduled_times_for_date,
    STATE_GROUPS,
)


def generate_crontab_lines(schedule: list) -> str:
    """
    Convert schedule entries into cron lines grouped by state pair.
    States within a group run at the same time (since they're staggered at submission, not UTC).
    """
    cron_lines = []
    
    # Group by (run_type, group, cron_hour, cron_minute) to get all states at each time slot
    time_slots = {}
    for entry in schedule:
        slot_key = (entry['run_type'], entry['group'], entry['cron_hour'], entry['cron_minute'])
        if slot_key not in time_slots:
            time_slots[slot_key] = []
        time_slots[slot_key].append(entry['state'])
    
    # Generate cron lines in order
    for (run_type, group, hour, minute), states in sorted(time_slots.items()):
        states_str = ', '.join(states)
        
        # Create comments and cron lines
        comment = f"# {run_type.upper()} Run - Group {group} ({states_str})"
        cron_command = (
            f"{minute} {hour} * * * cd /opt/council-news-bot && "
            f"docker compose run --rm bot python3 main.py --state {{state}} "
            f"--concurrency {{conc}} --time-window {run_type} >> /var/log/council_bot_scraper.log 2>&1"
        )
        
        cron_lines.append(comment)
        for state in states:
            # Generate two lines per state (one for each state in the pair)
            state_lower = state.lower()
            # Placeholder for dynamic concurrency (will be replaced in documentation)
            line = cron_command.replace('{state}', state_lower).replace('{conc}', '$(dynamic)')
            cron_lines.append(line)
        cron_lines.append("")
    
    return "\n".join(cron_lines)


def generate_crontab_static(schedule: list) -> str:
    """
    Generate a static crontab without placeholders.
    Determines concurrency based on state type.
    """
    from core.timezone_utils import get_recommended_concurrency
    
    cron_lines = []
    
    # Group by time slot
    time_slots = {}
    for entry in schedule:
        slot_key = (entry['run_type'], entry['group'], entry['cron_hour'], entry['cron_minute'])
        if slot_key not in time_slots:
            time_slots[slot_key] = []
        time_slots[slot_key].append(entry['state'])
    
    # Generate static cron lines
    for (run_type, group, hour, minute), states in sorted(time_slots.items()):
        states_str = ' + '.join(states)
        is_morning = run_type == 'morning'
        
        comment = f"# {run_type.upper()} - Group {group}: {states_str}"
        cron_lines.append(comment)
        
        for state in states:
            state_lower = state.lower()
            concurrency = get_recommended_concurrency(state, is_morning=is_morning)
            cron_cmd = (
                f"{minute} {hour} * * * cd /opt/council-news-bot && "
                f"docker compose run --rm bot python3 main.py --state {state_lower} "
                f"--concurrency {concurrency} --time-window {run_type} "
                f">> /var/log/council_bot_scraper.log 2>&1"
            )
            cron_lines.append(cron_cmd)
        
        cron_lines.append("")
    
    return "\n".join(cron_lines)


def get_crontab_header(reference_date: datetime = None) -> str:
    """Generate the crontab header with environment and documentation."""
    if reference_date is None:
        reference_date = datetime.now()
    
    return f"""# CRONTAB CONFIGURATION - Council News Bot (Twice-Daily Scraping)
# ====================================================================
# Generated on: {reference_date.strftime('%Y-%m-%d %H:%M:%S')}
# Reference Date: {reference_date.strftime('%Y-%m-%d')} (for UTC offset calculation)
#
# IMPORTANT NOTES:
# ================
# 1. All times below are in UTC (cron uses UTC on the VPS)
# 2. Times are calculated from local times:
#    - Morning: 06:00 local per state → UTC (varies by state & DST)
#    - Evening: 18:00 local per state → UTC (varies by state & DST)
#
# 3. State Time Zones:
#    - NSW, VIC, TAS, ACT: AEDT (UTC+11) or AEST (UTC+10) - Daylight Saving
#    - SA: ACDT (UTC+10:30) or ACST (UTC+9:30) - Daylight Saving
#    - QLD: AEST (UTC+10) - No Daylight Saving
#    - WA, NT: AWST (UTC+8) - No Daylight Saving
#
# 4. DST Transitions (Australian):
#    - SPRING FORWARD: First Sunday in October (UTC+1 hour)
#    - FALL BACK: First Sunday in April (UTC-1 hour)
#
# 5. Concurrency per state (gradual reduction 06:00-08:30 local):
#    - NSW, VIC, WA: 8 (off-peak) → 4 (morning)
#    - QLD, SA: 6 (off-peak) → 3 (morning)
#    - TAS, NT, ACT: 4 (off-peak) → 2 (morning)
#
# 6. Deployment:
#    a) SSH into VPS: ssh root@vps.example.com
#    b) Edit crontab: crontab -e
#    c) Paste this entire block below the environment section
#    d) Verify: crontab -l

# === ENVIRONMENT ===
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HOME=/root

# === SCRAPING SCHEDULE (Twice-Daily: 06:00 & 18:00 Local per State) ===

"""


def get_queue_processor_line() -> str:
    """Generate the cron line for the global queue processor."""
    return """# === POSTING QUEUE (Every 10 minutes) ===
# Processes backlog of articles and posts them to BlueSky.
# Reduced from 5-min to 10-min to conserve resources during twice-daily scraping.
*/10 * * * * cd /opt/council-news-bot && docker compose run --rm bot python3 scripts/cron/process_global_queue.py >> /var/log/council_bot_cron.log 2>&1

# === MONITORING & MAINTENANCE ===
# Hourly activity summary (posts, warnings, errors)
0 * * * * cd /opt/council-news-bot && docker compose run --rm bot python3 scripts/monitoring/hourly_briefing.py >> /var/log/council_bot_cron.log 2>&1

# Daily Briefing (21:00 UTC = 8:00 AM AEDT)
0 21 * * * cd /opt/council-news-bot && docker compose run --rm bot python3 scripts/monitoring/daily_briefing.py >> /var/log/council_bot_cron.log 2>&1

# Monthly cleanup (1st day at midnight UTC)
0 0 1 * * cd /opt/council-news-bot && docker compose run --rm bot python3 scripts/maintenance/cleanup_remote_db.py >> /var/log/council_bot_cron.log 2>&1

"""


def main():
    parser = argparse.ArgumentParser(
        description="Generate crontab entries for twice-daily scraping"
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Reference date for timezone calculation (YYYY-MM-DD, defaults to today)'
    )
    parser.add_argument(
        '--static',
        action='store_true',
        help='Generate static crontab with hardcoded concurrency (no placeholders)'
    )
    parser.add_argument(
        '--timeline-only',
        action='store_true',
        help='Generate just a timeline table (useful for documentation)'
    )
    
    args = parser.parse_args()
    
    # Parse reference date
    if args.date:
        try:
            ref_date = datetime.strptime(args.date, '%Y-%m-%d')
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.")
            sys.exit(1)
    else:
        ref_date = datetime.now()
    
    # Generate schedule
    schedule = get_scheduled_times_for_date(ref_date)
    
    if args.timeline_only:
        # Just print a formatted timeline
        print(f"\n=== Scheduled Scrape Times for {ref_date.date()} ===\n")
        print(f"{'Group':<6} {'State':<5} {'Run':<8} {'Local':<8} {'UTC Time':<12} {'Cron':<12}")
        print("=" * 65)
        for entry in sorted(schedule, key=lambda e: (e['run_type'], e['group'], e['state'])):
            cron = f"{entry['cron_minute']:02d} {entry['cron_hour']:02d}"
            print(
                f"{entry['group']:<6} {entry['state']:<5} {entry['run_type']:<8} "
                f"{entry['local_time']:<8} {entry['utc_time']:<12} {cron:<12}"
            )
        print()
        return
    
    # Generate full crontab
    header = get_crontab_header(ref_date)
    
    if args.static:
        scrape_section = generate_crontab_static(schedule)
    else:
        scrape_section = generate_crontab_lines(schedule)
    
    queue_section = get_queue_processor_line()
    
    full_crontab = header + scrape_section + queue_section
    
    print(full_crontab)
    
    # Also write to a file for reference
    output_file = PROJECT_ROOT / 'crontab_generated.txt'
    with open(output_file, 'w') as f:
        f.write(full_crontab)
    
    print(f"\n# Written to: {output_file}\n", file=sys.stderr)
    print(f"# Generated on: {datetime.now().isoformat()}", file=sys.stderr)
    print(f"# Reference date (for DST calculation): {ref_date.date()}", file=sys.stderr)


if __name__ == '__main__':
    main()

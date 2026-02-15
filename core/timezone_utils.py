#!/usr/bin/env python3
"""
Australian State Time Zone Utilities
--------------------------------------
Handles conversion of local times (06:00, 18:00 per state) to UTC for cron scheduling.
Accounts for daylight saving time transitions per state.

States & Time Zones:
- VIC, NSW, TAS, ACT: Eastern (AEDT UTC+11 / AEST UTC+10)
- SA: Central (ACDT UTC+10:30 / ACST UTC+9:30)
- WA, NT: Western (AWST UTC+8, no DST)

DST Transitions (Australian):
- Spring Forward: First Sunday in October → UTC+11/+10:30/+8
- Fall Back: First Sunday in April → UTC+10/+9:30/+8
"""

import pytz
from datetime import datetime, timedelta
from typing import Dict, Tuple, List
import os

# Australian state codes and their time zones
STATE_TIMEZONES = {
    'NSW': pytz.timezone('Australia/Sydney'),      # AEDT/AEST
    'VIC': pytz.timezone('Australia/Melbourne'),   # AEDT/AEST
    'TAS': pytz.timezone('Australia/Hobart'),      # AEDT/AEST
    'ACT': pytz.timezone('Australia/Sydney'),      # AEDT/AEST (shares Sydney tz)
    'SA': pytz.timezone('Australia/Adelaide'),     # ACDT/ACST
    'WA': pytz.timezone('Australia/Perth'),        # AWST (no DST)
    'NT': pytz.timezone('Australia/Darwin'),       # AWST (no DST)
    'QLD': pytz.timezone('Australia/Brisbane'),    # AEST (no DST in QLD)
}

# State grouping for load-balanced scheduling (2 states per group)
STATE_GROUPS = [
    ('NSW', 'VIC'),   # Group 1: High-load Eastern states
    ('QLD', 'TAS'),   # Group 2: QLD + Tasmania
    ('WA', 'SA'),     # Group 3: Western + South Australia
    ('NT', 'ACT'),    # Group 4: Northern Territory + ACT
]

# Morning and evening target times (local to each state)
MORNING_TIME = (6, 0)   # 06:00 local
EVENING_TIME = (18, 0)  # 18:00 local

# Stagger intervals: 30 minutes between each group
STAGGER_MINUTES = 30


def get_utc_time(state: str, local_hour: int, local_minute: int, reference_date: datetime = None) -> datetime:
    """
    Convert a local time (per state) to UTC.
    
    Args:
        state: State code ('NSW', 'VIC', 'SA', etc.)
        local_hour: Hour in local time (0-23)
        local_minute: Minute in local time (0-59)
        reference_date: Date to use for conversion (defaults to today)
    
    Returns:
        datetime object in UTC
    """
    if state not in STATE_TIMEZONES:
        raise ValueError(f"Unknown state: {state}")
    
    if reference_date is None:
        reference_date = datetime.now()
    
    tz = STATE_TIMEZONES[state]
    local_time = tz.localize(
        datetime(reference_date.year, reference_date.month, reference_date.day, local_hour, local_minute, 0)
    )
    utc_time = local_time.astimezone(pytz.UTC)
    return utc_time


def get_cron_time(state: str, local_hour: int, local_minute: int, reference_date: datetime = None) -> Tuple[int, int]:
    """
    Convert local time to cron-compatible UTC (hour, minute).
    
    Args:
        state: State code
        local_hour: Hour in local time
        local_minute: Minute in local time
        reference_date: Date for DST calculation (defaults to today)
    
    Returns:
        Tuple of (cron_hour, cron_minute) in UTC
    """
    utc_time = get_utc_time(state, local_hour, local_minute, reference_date)
    return (utc_time.hour, utc_time.minute)


def get_cron_expression(state: str, local_hour: int, local_minute: int, day_of_week: str = "*") -> str:
    """
    Generate a complete cron expression for a given state & local time.
    Note: Due to DST transitions, this is approximate and valid for ~6 months.
    For permanent accuracy, use dynamic generation (generate_crontab.py).
    
    Args:
        state: State code
        local_hour: Hour in local time
        local_minute: Minute in local time
        day_of_week: Cron day of week (default "*" = every day)
    
    Returns:
        Cron line string (minute hour * * day_of_week)
    """
    cron_minute, cron_hour = get_cron_time(state, local_hour, local_minute)
    return f"{cron_minute} {cron_hour} * * {day_of_week}"


def get_scheduled_times_for_date(date: datetime) -> List[Dict]:
    """
    Compute all scheduled scrape times (morning & evening) for a given date.
    Accounts for DST and state-specific time zones.
    
    Returns a list of dicts with:
    - state: State code
    - group: Group number (0-3)
    - local_time: "06:00" or "18:00"
    - cron_minute: UTC minute
    - cron_hour: UTC hour
    - utc_time: Formatted UTC time string
    """
    schedule = []
    
    for group_idx, (state1, state2) in enumerate(STATE_GROUPS):
        for run_type in ['morning', 'evening']:
            local_hour = MORNING_TIME[0] if run_type == 'morning' else EVENING_TIME[0]
            local_minute = MORNING_TIME[1] if run_type == 'morning' else EVENING_TIME[1]
            
            # Stagger each state group by (group_idx * 30 minutes)
            stagger_offset = timedelta(minutes=group_idx * STAGGER_MINUTES)
            staggered_date = date + stagger_offset
            
            for state in [state1, state2]:
                utc_time = get_utc_time(state, local_hour, local_minute, staggered_date)
                schedule.append({
                    'state': state,
                    'group': group_idx + 1,
                    'local_time': f"{local_hour:02d}:{local_minute:02d}",
                    'run_type': run_type,
                    'cron_hour': utc_time.hour,
                    'cron_minute': utc_time.minute,
                    'utc_time': utc_time.strftime('%H:%M UTC'),
                })
    
    return schedule


def is_morning_window(local_hour: int, local_minute: int) -> bool:
    """
    Check if a given local hour/minute is within the morning peak window (06:00-08:30).
    Used by main.py to apply reduced concurrency during morning scrapes.
    """
    morning_start = MORNING_TIME[0] * 60 + MORNING_TIME[1]  # 06:00 in minutes
    morning_end = 8 * 60 + 30  # 08:30 in minutes
    current_time = local_hour * 60 + local_minute
    return morning_start <= current_time <= morning_end


def get_recommended_concurrency(state: str, is_morning: bool = False) -> int:
    """
    Return recommended concurrency for a state based on time of day.
    
    Morning peak (06:00-08:30): Reduced concurrency to avoid proxy/network strain.
    - High-load states (NSW, VIC): concurrency 4
    - Medium-load states (QLD, WA, SA): concurrency 3
    - Low-load states (TAS, NT, ACT): concurrency 2
    
    Off-peak: Standard concurrency.
    - High-load: 8
    - Medium-load: 6
    - Low-load: 4
    """
    high_load = ['NSW', 'VIC', 'WA']
    medium_load = ['QLD', 'SA']
    low_load = ['TAS', 'NT', 'ACT']
    
    if state in high_load:
        return 4 if is_morning else 8
    elif state in medium_load:
        return 3 if is_morning else 6
    elif state in low_load:
        return 2 if is_morning else 4
    else:
        return 6  # Default fallback


if __name__ == '__main__':
    # Quick test: Print today's scheduled times
    today = datetime.now()
    print(f"\n=== Scheduled Scrape Times for {today.date()} ===\n")
    
    schedule = get_scheduled_times_for_date(today)
    
    for entry in schedule:
        print(
            f"{entry['group']}.{entry['state']:3} | "
            f"{entry['run_type']:7} | "
            f"Local: {entry['local_time']} | "
            f"UTC: {entry['utc_time']:12} | "
            f"Cron: {entry['cron_minute']:2d} {entry['cron_hour']:2d} * * *"
        )
    
    print(f"\n=== Test: UTC conversion for a few states ===\n")
    for state in ['NSW', 'SA', 'WA']:
        utc_morning = get_utc_time(state, 6, 0, today)
        utc_evening = get_utc_time(state, 18, 0, today)
        print(f"{state}: 06:00 local → {utc_morning.strftime('%H:%M UTC')}, "
              f"18:00 local → {utc_evening.strftime('%H:%M UTC')}")

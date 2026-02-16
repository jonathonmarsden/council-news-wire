#!/usr/bin/env python3
"""
Global Post Queue Processor
---------------------------
Designed to be run by Cron every 10 minutes (reduced from 5-min for twice-daily scraping).
Iterates through all configured states and posts pending articles from the backlog.

Usage:
    python3 scripts/cron/process_global_queue.py

Cron Entry:
    */10 * * * * cd /opt/council-news-bot && docker compose run --rm bot python3 scripts/cron/process_global_queue.py
"""

import sys
import os
import subprocess
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

def get_configured_states():
    """Scan the states directory for valid configs."""
    states_dir = PROJECT_ROOT / 'states'
    states = []
    if not states_dir.exists():
        return []
    
    for item in states_dir.iterdir():
        if item.is_dir() and not item.name.startswith('_'):
            # Check if it has a councils.json
            if (item / 'councils.json').exists():
                states.append(item.name.upper())
    return sorted(states)

def process_state(state):
    """Run the main.py post-only mode for a state."""
    print(f"--- Processing Queue: {state} ---")
    try:
        # Run main.py in post-only mode
        # Limits: Post max 3 items per cron run (75% of BlueSky 24/hr limit)
        # This runs every 10 mins, so 3 * 6 = 18 posts per hour per state max.
        # System capacity: 18/hr × 8 states = 144 posts/hr (vs previous 96/hr)
        cmd = [
            sys.executable, 
            str(PROJECT_ROOT / 'main.py'),
            '--state', state,
            '--post-only',
            '--limit', '3',  
            '--max-per-council', '1' 
        ]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            timeout=120 # 2 minute timeout per state
        )
        
        # Log simplified output
        for line in result.stdout.split('\n'):
            if "Posted" in line or "Error" in line:
                print(f"[{state}] {line.strip()}")
        
        if result.stderr:
            print(f"[{state} STDERR] {result.stderr.strip()}")
            
    except subprocess.TimeoutExpired:
        print(f"[{state}] Timed out.")
    except Exception as e:
        print(f"[{state}] Failed: {e}")

def main():
    start_time = time.time()
    states = get_configured_states()
    print(f"Global Queue Processor started for: {', '.join(states)}")
    
    for state in states:
        process_state(state)
        
    duration = time.time() - start_time
    print(f"Done in {duration:.2f}s")

if __name__ == "__main__":
    main()

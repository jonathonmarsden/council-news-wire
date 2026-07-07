#!/usr/bin/env python3
"""
Global Post Queue Processor
---------------------------
Designed to be run by Cron every 10 minutes (reduced from 5-min for twice-daily scraping).
Iterates through all configured states and posts pending articles from the backlog.

Usage:
    python3 scripts/cron/process_global_queue.py

Cron Entry:
    */10 * * * * cd /opt/council-news-bot && docker compose exec -T bot python3 scripts/cron/process_global_queue.py
"""

import fcntl
import sys
import os
import subprocess
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

# Prevents overlapping processor instances (worst case 8 states x 120s
# exceeds the 10-min cron period). NOTE: cron launches this via
# `docker compose run` (fresh container, fresh /tmp), so cross-tick
# protection comes from the host-level `flock -n` in the generated cron
# line; this in-process lock only guards same-filesystem invocations.
LOCK_FILE = '/tmp/council_queue_processor.lock'


def acquire_lock():
    """Return a held lock file handle, or None if another instance runs."""
    fh = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except (IOError, OSError):
        fh.close()
        return None

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
        
        # SIGTERM with a grace period rather than subprocess.run's SIGKILL —
        # a kill between send_post and the DB update would repost next tick.
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = proc.communicate(timeout=120)  # 2 minute timeout per state
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                stdout, stderr = proc.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
            print(f"[{state}] Timed out.")

        # Post-only output is small; relay everything so failures
        # (auth errors, validation rejections, transient breaks) are visible.
        for line in stdout.split('\n'):
            if line.strip():
                print(f"[{state}] {line.strip()}")

        if stderr:
            print(f"[{state} STDERR] {stderr.strip()}")

    except Exception as e:
        print(f"[{state}] Failed: {e}")

def main():
    lock = acquire_lock()
    if lock is None:
        print("Another queue processor instance is still running; exiting.")
        return

    start_time = time.time()
    states = get_configured_states()
    print(f"Global Queue Processor started for: {', '.join(states)}")

    for state in states:
        process_state(state)

    duration = time.time() - start_time
    print(f"Done in {duration:.2f}s")

if __name__ == "__main__":
    main()

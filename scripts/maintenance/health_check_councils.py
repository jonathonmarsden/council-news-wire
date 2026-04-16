#!/usr/bin/env python3
"""
Council Health Check — Daily Scraper Status Report

Lists all councils with persistent empty runs or errors so broken scrapers
can be identified and fixed quickly.

Usage:
    python3 scripts/maintenance/health_check_councils.py
    python3 scripts/maintenance/health_check_councils.py --state sa
    python3 scripts/maintenance/health_check_councils.py --threshold 5

Exit code 0 = all healthy, 1 = issues found (suitable for CI/monitoring).
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')


def load_council_names() -> dict:
    """Build a map of council_id -> name from all state configs."""
    import json
    names = {}
    states_dir = PROJECT_ROOT / 'states'
    for state_dir in states_dir.iterdir():
        if not state_dir.is_dir() or state_dir.name.startswith('_'):
            continue
        councils_file = state_dir / 'councils.json'
        if not councils_file.exists():
            continue
        try:
            with open(councils_file) as f:
                data = json.load(f)
            for c in data.get('councils', []):
                names[c['id']] = (c.get('name', c['id']), state_dir.name.upper())
        except Exception:
            pass
    return names


def main():
    parser = argparse.ArgumentParser(description='Council scraper health check')
    parser.add_argument('--state', type=str, help='Filter to one state (e.g. sa)')
    parser.add_argument('--threshold', type=int, default=5,
                        help='Min consecutive empty runs to flag (default: 5)')
    args = parser.parse_args()

    from core.database import Database
    db = Database()
    council_names = load_council_names()

    with db.get_session() as session:
        from sqlalchemy import text
        rows = session.execute(text("""
            SELECT
                ch.council_id,
                ch.consecutive_failures,
                ch.consecutive_empty_runs,
                ch.is_disabled,
                ch.last_success_at,
                ch.last_failure_at,
                ch.disabled_at,
                (SELECT count(*) FROM articles a WHERE a.council_id = ch.council_id) as total_articles,
                (SELECT max(a.first_seen_at) FROM articles a WHERE a.council_id = ch.council_id) as last_article_seen
            FROM council_health ch
            WHERE ch.is_disabled = true
               OR ch.consecutive_failures >= 3
               OR ch.consecutive_empty_runs >= :threshold
            ORDER BY ch.is_disabled DESC,
                     ch.consecutive_empty_runs DESC,
                     ch.consecutive_failures DESC
        """), {'threshold': args.threshold}).fetchall()

    if not rows:
        print("✅ All councils healthy — no issues detected.")
        sys.exit(0)

    # Filter by state if requested
    if args.state:
        state_filter = args.state.upper()
        rows = [r for r in rows if council_names.get(r.council_id, ('', ''))[1] == state_filter]

    disabled = [r for r in rows if r.is_disabled]
    empty = [r for r in rows if not r.is_disabled and r.consecutive_empty_runs >= args.threshold]
    failing = [r for r in rows if not r.is_disabled and r.consecutive_failures >= 3]

    now = datetime.now()

    def age(dt):
        if not dt:
            return 'never'
        delta = now - dt
        if delta.days > 0:
            return f"{delta.days}d ago"
        return f"{delta.seconds // 3600}h ago"

    if disabled:
        print(f"\n🔴 DISABLED COUNCILS ({len(disabled)}) — circuit breaker tripped:")
        print(f"  {'Council':<35} {'State':<6} {'Reason':<25} {'Disabled'}")
        print(f"  {'-'*35} {'-'*6} {'-'*25} {'-'*15}")
        for r in disabled:
            name, state = council_names.get(r.council_id, (r.council_id, '?'))
            reason = f"{r.consecutive_empty_runs} empty runs" if r.consecutive_empty_runs >= args.threshold else f"{r.consecutive_failures} failures"
            print(f"  {name[:35]:<35} {state:<6} {reason:<25} {age(r.disabled_at)}")

    if empty:
        print(f"\n🟡 PERSISTENT EMPTY SCRAPERS ({len(empty)}) — returning 0 articles consistently:")
        print(f"  {'Council':<35} {'State':<6} {'Empty Runs':<12} {'Last Article'}")
        print(f"  {'-'*35} {'-'*6} {'-'*12} {'-'*15}")
        for r in empty:
            name, state = council_names.get(r.council_id, (r.council_id, '?'))
            last = age(r.last_article_seen) if r.last_article_seen else 'never'
            print(f"  {name[:35]:<35} {state:<6} {r.consecutive_empty_runs:<12} {last}")

    if failing:
        print(f"\n🔴 FAILING SCRAPERS ({len(failing)}) — returning errors:")
        print(f"  {'Council':<35} {'State':<6} {'Failures':<10} {'Last Failure'}")
        print(f"  {'-'*35} {'-'*6} {'-'*10} {'-'*15}")
        for r in failing:
            name, state = council_names.get(r.council_id, (r.council_id, '?'))
            print(f"  {name[:35]:<35} {state:<6} {r.consecutive_failures:<10} {age(r.last_failure_at)}")

    total_issues = len(disabled) + len(empty) + len(failing)
    print(f"\nTotal issues: {total_issues} councils")
    sys.exit(1)


if __name__ == '__main__':
    main()

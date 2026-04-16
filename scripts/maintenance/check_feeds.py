#!/usr/bin/env python3
"""
Check all BlueSky state feeds for recent activity.

Usage:
    python3 scripts/maintenance/check_feeds.py
    python3 scripts/maintenance/check_feeds.py --limit 5
    python3 scripts/maintenance/check_feeds.py --state vic
"""

import argparse
import json
import sys
import time
from pathlib import Path
import urllib.request
import urllib.error

PROJECT_ROOT = Path(__file__).resolve().parents[2]

HANDLES = {
    "VIC": "roundupnewsbotvic.bsky.social",
    "NSW": "roundupnewsbotnsw.bsky.social",
    "QLD": "roundupnewsbotqld.bsky.social",
    "SA":  "roundupnewsbotsa.bsky.social",
    "WA":  "roundupnewsbotwa.bsky.social",
    "TAS": "roundupnewsbottas.bsky.social",
    "NT":  "roundupnewsbotnt.bsky.social",
    "ACT": "roundupnewsbotact.bsky.social",
}

BSKY_API = "https://public.api.bsky.app/xrpc"


def fetch_feed(handle: str, limit: int = 5) -> dict:
    url = f"{BSKY_API}/app.bsky.feed.getAuthorFeed?actor={handle}&limit={limit}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


STALE_THRESHOLD_HOURS = 48


def check_state(state: str, handle: str, limit: int) -> bool:
    """Returns True if feed is healthy, False if stale or errored."""
    print(f"\n{'='*60}")
    print(f"  {state} — @{handle}")
    print(f"{'='*60}")

    data = fetch_feed(handle, limit)

    if "error" in data:
        print(f"  ERROR: {data['error']}")
        return False

    feed = data.get("feed", [])
    if not feed:
        print("  ⚠️  NO POSTS FOUND")
        return False

    # Check staleness of most recent post
    from datetime import timezone
    latest_post = feed[0].get("post", {})
    latest_indexed = latest_post.get("indexedAt", "")
    is_stale = False
    if latest_indexed:
        try:
            from datetime import datetime
            latest_dt = datetime.fromisoformat(latest_indexed.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - latest_dt).total_seconds() / 3600
            if age_hours > STALE_THRESHOLD_HOURS:
                is_stale = True
                print(f"  ⚠️  STALE — last post was {age_hours:.0f}h ago (threshold: {STALE_THRESHOLD_HOURS}h)")
        except Exception:
            pass

    print(f"  {len(feed)} posts retrieved (showing up to {limit})" + ("" if not is_stale else " — STALE") + "\n")
    for item in feed:
        post = item.get("post", {})
        record = post.get("record", {})
        indexed = post.get("indexedAt", "?")[:19].replace("T", " ")
        text = record.get("text", "").replace("\n", " ")[:90]
        uri = post.get("uri", "")
        print(f"  [{indexed}] {text}")
        print(f"  └─ {uri}")
        print()

    return not is_stale


def main():
    parser = argparse.ArgumentParser(description="Check BlueSky state feeds")
    parser.add_argument("--limit", type=int, default=3, help="Posts to show per feed (default: 3)")
    parser.add_argument("--state", type=str, help="Check a single state only (e.g. vic)")
    args = parser.parse_args()

    if args.state:
        state = args.state.upper()
        if state not in HANDLES:
            print(f"Unknown state '{state}'. Valid: {', '.join(HANDLES)}")
            sys.exit(1)
        states = {state: HANDLES[state]}
    else:
        states = HANDLES

    print(f"Council News Bot — BlueSky Feed Status Check")
    print(f"Checking {len(states)} feed(s) via {BSKY_API}")

    stale = []
    for state, handle in states.items():
        ok = check_state(state, handle, args.limit)
        if not ok:
            stale.append(state)
        time.sleep(0.3)  # be polite to the API

    print(f"\n{'='*60}")
    if stale:
        print(f"⚠️  STALE/ERRORED FEEDS: {', '.join(stale)}")
        sys.exit(1)
    else:
        print("✅ All feeds healthy.")
        sys.exit(0)


if __name__ == "__main__":
    main()

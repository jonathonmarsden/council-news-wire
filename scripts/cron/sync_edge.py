#!/usr/bin/env python3
"""Send newly posted stories to the edge service (Bluesky custom feeds + RSS).

The edge keeps its own copy of what the bot has published, so feeds and RSS
keep serving when this host is down. This script sends it every story posted
since the last successful sync (with an hour of overlap; the edge upserts by
URL, so repeats are harmless), and asks it to drop stories older than
PRUNE_DAYS.

Silent no-op until EDGE_INGEST_TOKEN is set, so it can be scheduled before
the edge service exists. The last sync time is kept in monitor_state.

Usage:
    python3 scripts/cron/sync_edge.py
    python3 scripts/cron/sync_edge.py --dry-run          # count, send nothing
    python3 scripts/cron/sync_edge.py --dump out.json    # write the payload, send nothing
    python3 scripts/cron/sync_edge.py --since 2026-08-01 # resend from a date
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

STATE_KEY = "edge_sync"
DEFAULT_URL = "https://councilnewswire.au/ingest"
FIRST_SYNC_DAYS = 90
PRUNE_DAYS = 120
# Pruning scans the whole edge table (it keeps each council's latest stories
# however old), so it runs once a day, on the first sync of this UTC hour
# (16:00 UTC is 2-3am in eastern Australia), not every ten minutes.
PRUNE_HOUR_UTC = 16
# D1's free plan allows 100,000 row writes a day, and every story written also
# counts once per index (about 4 writes per story). A manual --since resend
# larger than this needs --allow-large, and should be spread over days.
MAX_MANUAL_ROWS = 10_000


def prune_due(now: datetime) -> bool:
    return now.hour == PRUNE_HOUR_UTC and now.minute < 10
OVERLAP = timedelta(hours=1)
BATCH = 400
AU = ZoneInfo("Australia/Sydney")


def council_names(states_dir: Path = ROOT / "states") -> Dict[str, str]:
    names = {}
    for path in sorted(states_dir.glob("*/councils.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for c in raw["councils"] if isinstance(raw, dict) else raw:
            names[c["id"]] = c["name"]
    return names


def iso_utc(dt: Optional[datetime], naive_tz=timezone.utc) -> Optional[str]:
    """ISO 8601 in UTC. Naive datetimes are read as `naive_tz`."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=naive_tz)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_payload(a, names: Dict[str, str]) -> Optional[Dict]:
    """One article row as the edge expects it, or None if it lacks essentials."""
    if not a.url or not a.title or not a.posted_at:
        return None
    excerpt = (a.excerpt or a.og_description or "").strip()
    return {
        "url": a.url,
        "uri": a.bluesky_uri,
        "council_id": a.council_id,
        "council_name": names.get(a.council_id, a.council_id),
        "state": (a.state or "").lower(),
        "title": a.title.strip(),
        "excerpt": excerpt[:400] or None,
        # posted_at is stored in UTC; council dates are Australian local time.
        "published_at": iso_utc(a.date, AU),
        "posted_at": iso_utc(a.posted_at),
    }


def batches(items: List[Dict], size: int = BATCH) -> Iterable[List[Dict]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def send(url: str, token: str, body: Dict) -> Dict:
    import requests
    r = requests.post(url, json=body, timeout=60,
                      headers={"Authorization": f"Bearer {token}", "User-Agent": "council-news-bot edge-sync"})
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dump", type=Path)
    ap.add_argument("--since", help="resend everything posted since this date (YYYY-MM-DD)")
    ap.add_argument("--allow-large", action="store_true",
                    help=f"allow a --since resend of more than {MAX_MANUAL_ROWS} stories (D1 write budget)")
    args = ap.parse_args()

    token = os.environ.get("EDGE_INGEST_TOKEN", "")
    url = os.environ.get("EDGE_INGEST_URL", DEFAULT_URL)
    if not token and not (args.dry_run or args.dump):
        print("EDGE_INGEST_TOKEN not set; edge sync skipped.")
        return 0

    from core.database import Database
    from core.models import Article
    from core.monitor_state import load_state, save_state

    db = Database()
    now = datetime.utcnow()
    saved = load_state(db, STATE_KEY) or {}
    if args.since:
        since = datetime.fromisoformat(args.since)
    elif saved.get("through"):
        since = datetime.fromisoformat(saved["through"].rstrip("Z")) - OVERLAP
    else:
        since = now - timedelta(days=FIRST_SYNC_DAYS)

    names = council_names()
    with db.get_session() as s:
        rows = (s.query(Article).filter(Article.posted_at.isnot(None), Article.posted_at > since)
                .order_by(Article.posted_at).all())
        payload = [p for p in (to_payload(a, names) for a in rows) if p]

    if args.since and len(payload) > MAX_MANUAL_ROWS and not args.allow_large:
        print(f"Refusing to resend {len(payload)} stories: about {len(payload) * 4} D1 row writes against a "
              f"100,000/day free limit. Use a later --since, or --allow-large if you mean it.")
        return 2
    prune_before = iso_utc(now - timedelta(days=PRUNE_DAYS))
    print(f"Edge sync {now:%Y-%m-%d %H:%M} UTC: {len(payload)} stories posted since {since:%Y-%m-%d %H:%M}")
    if args.dump:
        args.dump.write_text(json.dumps({"posts": payload, "prune_before": prune_before}, indent=1))
        print(f"wrote {args.dump}")
        return 0
    if args.dry_run:
        return 0

    accepted = rejected = 0
    first = True
    for chunk in batches(payload) if payload else [[]]:
        body = {"posts": chunk}
        if first and prune_due(now):
            body["prune_before"] = prune_before
        first = False
        out = send(url, token, body)
        accepted += out.get("accepted", 0)
        rejected += out.get("rejected", 0)
    through = payload[-1]["posted_at"] if payload else saved.get("through") or iso_utc(since)
    save_state(db, STATE_KEY, {"through": through, "at": iso_utc(now), "last_accepted": accepted, "last_rejected": rejected})
    print(f"  accepted {accepted}, rejected {rejected}; synced through {through}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

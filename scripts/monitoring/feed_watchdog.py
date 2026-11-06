#!/usr/bin/env python3
"""
Feed watchdog: is each feed still carrying a broad spread of councils?

Reads the public Bluesky feeds and alerts to DISCORD_WEBHOOK_ALERTS when far
fewer distinct councils appear in a state's recent posts than the state has
enabled. That catches a quiet mass failure that does not stop a feed outright,
which a "when was the last post" check cannot see.

Staleness ("this feed has stopped posting") is no longer checked here. The
off-host watchdog checks every feed every 15 minutes, still works when this
host is down, and uses per-state limits that ignore weekends. The wall-clock
limits that used to live here fired on most Sundays.

Reports changes only: a state is reported when its coverage drops below the
floor and again when it recovers, not on every run. What was last reported is
kept in the monitor_state table. A feed that cannot be read is printed but not
alerted on; one timeout used to produce an alert.

Usage:
    python3 scripts/monitoring/feed_watchdog.py
    python3 scripts/monitoring/feed_watchdog.py --coverage-floor 0.25 --dry-run
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HANDLES = {
    "VIC": "roundupnewsbotvic.bsky.social", "NSW": "roundupnewsbotnsw.bsky.social",
    "QLD": "roundupnewsbotqld.bsky.social", "SA": "roundupnewsbotsa.bsky.social",
    "WA": "roundupnewsbotwa.bsky.social", "TAS": "roundupnewsbottas.bsky.social",
    "NT": "roundupnewsbotnt.bsky.social", "ACT": "roundupnewsbotact.bsky.social",
}
API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
SUFFIXES = ["regional council", "shire council", "city council", "municipal council",
            "district council", "town council", "aboriginal shire", "council", "shire",
            "city of", "the ", "regional"]
RED = 15158332  # Discord embed colours
GREEN = 3066993
STATE_KEY = "feed_watchdog"


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def shortkey(name):
    n = (name or "").lower()
    for w in SUFFIXES:
        n = n.replace(w, " ")
    return norm(n)


def pull(handle, rounds):
    posts, cursor = [], None
    for _ in range(rounds):
        url = f"{API}?actor={handle}&limit=100" + (f"&cursor={cursor}" if cursor else "")
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
        except Exception as e:
            return posts, str(e)
        posts += data.get("feed", [])
        cursor = data.get("cursor")
        if not cursor:
            break
        time.sleep(0.25)
    return posts, None


def check(coverage_floor, depth):
    """(findings, lines): thin-coverage findings by stable key, and a report."""
    findings = {}
    lines = []
    for st, handle in HANDLES.items():
        councils = [c for c in json.load(open(ROOT / f"states/{st.lower()}/councils.json"))["councils"]
                    if c.get("enabled")]
        posts, err = pull(handle, depth)
        if err or not posts:
            lines.append(f"{st}: could not read feed ({err or 'empty'})")
            continue

        latest = max(p["post"].get("indexedAt", "") for p in posts)
        text = " ".join(norm(p["post"]["record"].get("text", "")) for p in posts)
        seen = sum(1 for c in councils
                   if (len(norm(c["name"])) > 6 and norm(c["name"]) in text)
                   or (len(shortkey(c["name"])) >= 5 and shortkey(c["name"]) in text))
        coverage = seen / len(councils) if councils else 0

        thin = len(councils) >= 10 and coverage < coverage_floor  # only for multi-council states
        if thin:
            findings[f"thin:{st}"] = {
                "msg": (f"{st}: only {seen} of {len(councils)} councils appear in the last "
                        f"{len(posts)} posts ({coverage:.0%}, floor {coverage_floor:.0%})"),
                "ok": f"{st}: coverage back to {seen} of {len(councils)} councils ({coverage:.0%})",
            }
        lines.append(f"{st}: {seen}/{len(councils)} councils, latest {latest[:16] or '?'}"
                     + ("  [THIN]" if thin else "  ok"))
    return findings, lines


def build_message(opened, cleared, now):
    if not opened and not cleared:
        return None
    body = [f"⚠️ {f['msg']}" for _, f in sorted(opened.items())]
    body += [f"✅ {f['ok']}" for _, f in sorted(cleared.items())]
    return {
        "title": "Feed watchdog: council coverage dropped" if opened else "Feed watchdog: coverage recovered",
        "description": "\n".join(body)[:4000],
        "color": RED if opened else GREEN,
        "timestamp": now.isoformat(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coverage-floor", type=float, default=0.20,
                    help="alert if represented-council fraction drops below this (default 0.20)")
    ap.add_argument("--depth", type=int, default=6, help="feed pages to pull (x100 posts)")
    ap.add_argument("--dry-run", action="store_true", help="print only: send nothing, save nothing")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    findings, lines = check(args.coverage_floor, args.depth)
    print("Feed watchdog", now.strftime("%Y-%m-%d %H:%M UTC"))
    for ln in lines:
        print("  " + ln)
    if args.dry_run:
        return

    from core.database import Database
    from core.monitor_state import load_state, save_state, diff_findings
    db = Database()
    saved = load_state(db, STATE_KEY)
    opened, cleared = diff_findings((saved or {}).get("findings", {}), findings)
    embed = build_message(opened, cleared, now)
    if embed:
        from discord_logger import send_discord_embed, DISCORD_WEBHOOK_ALERTS
        if not send_discord_embed(DISCORD_WEBHOOK_ALERTS, embed):
            print("Discord did not accept the alert; state not saved, will retry next run.")
            sys.exit(1)
        print("Sent: " + embed["title"])
    if embed or saved is None:
        save_state(db, STATE_KEY, {"findings": findings, "at": now.isoformat()})
    sys.exit(1 if findings else 0)


def _crash_alert(exc: Exception) -> None:
    """The watchdog watching nothing is itself an alert-worthy failure."""
    try:
        from discord_logger import send_discord_embed, DISCORD_WEBHOOK_ALERTS
        send_discord_embed(DISCORD_WEBHOOK_ALERTS, {
            "title": "🔴 feed_watchdog CRASHED",
            "description": f"The feed watchdog itself failed — output monitoring is blind.\n"
                           f"`{type(exc).__name__}: {exc}`"[:4000],
            "color": RED,
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"feed_watchdog crashed: {type(e).__name__}: {e}")
        _crash_alert(e)
        sys.exit(2)

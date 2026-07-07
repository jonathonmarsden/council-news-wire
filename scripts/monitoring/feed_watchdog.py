#!/usr/bin/env python3
"""
Feed watchdog — the output-side health check.

The bot's circuit breaker and briefings track "did the scraper run", but the
ground-truth signal is "what actually got published to BlueSky". Nothing watched
that automatically, which is why the proxy lapse, the ~April-16 mass auto-disable
(85 councils), and the 82-day ACT outage all went unnoticed for weeks-to-months.

This script, run on a schedule (every few hours), checks the BlueSky feeds
directly and alerts to Discord (DISCORD_WEBHOOK_ALERTS) when output looks wrong:

  1. STALE FEED      — a state feed's latest post is older than --stale-hours.
  2. THIN COVERAGE   — far fewer distinct councils represented in the recent
                       window than the state has enabled (catches a quiet
                       mass-failure that doesn't fully stop a feed).

It is read-only (public BlueSky API + local config only) and degrades gracefully
when Discord isn't configured — it just prints. Pair it with the deeper
scripts/maintenance/triage_coverage.py for on-demand per-council diagnosis.

Usage:
    python3 scripts/monitoring/feed_watchdog.py
    python3 scripts/monitoring/feed_watchdog.py --stale-hours 24 --coverage-floor 0.25
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
# Low-volume states are legitimately quiet for longer (few councils, slow
# weekends) — a flat 24h threshold re-alerts every 4h and trains channel
# blindness, which is what quiet-by-default was meant to fix.
STALE_HOURS_OVERRIDE = {"TAS": 48.0, "NT": 48.0, "ACT": 48.0}
# Re-alerting an UNCHANGED problem set is suppressed for this long.
COOLDOWN_FILE = ROOT / "logs" / ".watchdog_last_alert"
COOLDOWN_HOURS = 24.0
SUFFIXES = ["regional council", "shire council", "city council", "municipal council",
            "district council", "town council", "aboriginal shire", "council", "shire",
            "city of", "the ", "regional"]
RED = 15158332  # Discord embed colour for alerts


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


def check(stale_hours, coverage_floor, depth):
    now = datetime.now(timezone.utc)
    problems = []
    lines = []
    for st, handle in HANDLES.items():
        councils = [c for c in json.load(open(ROOT / f"states/{st.lower()}/councils.json"))["councils"]
                    if c.get("enabled")]
        posts, err = pull(handle, depth)
        if err or not posts:
            problems.append(f"**{st}**: feed error / no posts ({err or 'empty'})")
            lines.append(f"{st}: ERROR {err or 'empty'}")
            continue

        latest = max(p["post"].get("indexedAt", "") for p in posts)
        try:
            age_h = (now - datetime.fromisoformat(latest.replace("Z", "+00:00"))).total_seconds() / 3600
        except Exception:
            age_h = None

        text = " ".join(norm(p["post"]["record"].get("text", "")) for p in posts)
        seen = sum(1 for c in councils
                   if (len(norm(c["name"])) > 6 and norm(c["name"]) in text)
                   or (len(shortkey(c["name"])) >= 5 and shortkey(c["name"]) in text))
        coverage = seen / len(councils) if councils else 0

        flags = []
        st_stale = STALE_HOURS_OVERRIDE.get(st, stale_hours)
        if age_h is not None and age_h > st_stale:
            flags.append(f"STALE {age_h:.0f}h")
            problems.append(f"**{st}**: stale — last post {age_h:.0f}h ago (>{st_stale:.0f}h)")
        # Coverage floor only meaningful for multi-council states.
        if len(councils) >= 10 and coverage < coverage_floor:
            flags.append(f"THIN {coverage:.0%}")
            problems.append(f"**{st}**: thin coverage — {seen}/{len(councils)} councils "
                            f"in last {len(posts)} posts ({coverage:.0%} < {coverage_floor:.0%})")
        lines.append(f"{st}: {seen}/{len(councils)} councils, latest "
                     f"{(latest[:16] if latest else '?')}"
                     + (f"  [{', '.join(flags)}]" if flags else "  ok"))
    return problems, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stale-hours", type=float, default=24.0,
                    help="alert if a feed's latest post is older than this (default 24)")
    ap.add_argument("--coverage-floor", type=float, default=0.20,
                    help="alert if represented-council fraction drops below this (default 0.20)")
    ap.add_argument("--depth", type=int, default=6, help="feed pages to pull (x100 posts)")
    args = ap.parse_args()

    problems, lines = check(args.stale_hours, args.coverage_floor, args.depth)

    print("Feed watchdog —", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    for ln in lines:
        print("  " + ln)

    if problems:
        body = "\n".join(f"• {p}" for p in problems)
        print("\nALERT:\n" + body)
        if _in_cooldown(problems):
            print("(unchanged problem set — Discord re-alert suppressed by cooldown)")
        else:
            try:
                from discord_logger import send_discord_embed, DISCORD_WEBHOOK_ALERTS
                send_discord_embed(DISCORD_WEBHOOK_ALERTS, {
                    "title": "🚨 Feed watchdog: output looks wrong",
                    "description": body[:4000],
                    "color": RED,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                _record_alert(problems)
            except Exception as e:
                print(f"(Discord alert not sent: {e})")
        sys.exit(1)

    _clear_cooldown()
    print("\n✅ All feeds fresh and representative.")
    sys.exit(0)


def _problems_hash(problems):
    import hashlib
    return hashlib.md5("\n".join(sorted(problems)).encode()).hexdigest()


def _in_cooldown(problems) -> bool:
    try:
        state = json.loads(COOLDOWN_FILE.read_text())
        age_h = time.time() / 3600 - state["ts_hours"]
        return state["hash"] == _problems_hash(problems) and age_h < COOLDOWN_HOURS
    except Exception:
        return False


def _record_alert(problems) -> None:
    try:
        COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOLDOWN_FILE.write_text(json.dumps(
            {"hash": _problems_hash(problems), "ts_hours": time.time() / 3600}))
    except Exception as e:
        print(f"(cooldown state not written: {e})")


def _clear_cooldown() -> None:
    try:
        COOLDOWN_FILE.unlink()
    except Exception:
        pass


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

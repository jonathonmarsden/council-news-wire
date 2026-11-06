#!/usr/bin/env python3
"""
Alert check: the internal-state detector, reporting changes only.

Watches the database for the failure modes that have slipped past before, and
posts to DISCORD_WEBHOOK_ALERTS only when a problem OPENS or CLEARS. A problem
that is still open is not repeated: the earlier version alerted on every run
for weeks (the same "empty runs" notice four times a day), which taught
readers to ignore the channel. Open problems are remembered in the
monitor_state table.

Findings, each with a stable key:

  disabled:<council>  council switched off by the circuit breaker. A failed
                      probation retry keeps it switched off, so it is not
                      reported again; it clears when the council comes back.
  infra               proxy / Bluesky auth failures in log_events in the window
                      (the proxy lapse was silent for ~10 days).
  missed_runs:<STATE> no scrape runs for a state in 24h (wedged cron/docker or
                      a bad crontab install); missed_runs:ALL when every state.
  queue_stalled       articles queued for hours while nothing posts.

Not here any more, on purpose:
  - feeds going quiet: the off-host watchdog checks the public feeds every
    15 minutes against per-state limits that ignore weekends; a 12h
    wall-clock check here fired most Sundays.
  - councils with a run of empty scrapes: the breaker switches them off at
    its own threshold (reported here as disabled:), and the weekly coverage
    ledger lists councils that are quiet or overdue.

Read-only apart from its own row in monitor_state. If Discord does not accept
the message, the state is not saved, so the next run reports it again.

Usage:
    python3 scripts/monitoring/alert_check.py
    python3 scripts/monitoring/alert_check.py --dry-run   # print, send nothing, save nothing
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Set

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RED = 15158332
ORANGE = 15105570
GREEN = 3066993
STATE_KEY = "alert_check"
ALL_STATES = ["nsw", "vic", "qld", "wa", "sa", "tas", "nt", "act"]
DISABLE_FAILURES = 5  # Database.record_failure disables at this many errors
INFRA_PATTERN = re.compile(
    r"\b(402\b|payment required|proxy|unauthori[sz]ed|authenticat|login\b|invalid identifier or password)",
    re.IGNORECASE)


def enabled_council_ids(states_dir: Path = ROOT / "states") -> Set[str]:
    """Ids of councils enabled in config; breaker rows for anything else
    (removed or switched off in config) are not problems to report."""
    ids = set()
    for path in sorted(states_dir.glob("*/councils.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for c in raw["councils"] if isinstance(raw, dict) else raw:
            if c.get("enabled", True):
                ids.add(c["id"])
    return ids


def collect_findings(session, now: datetime, window_hours: float,
                     enabled: Optional[Set[str]] = None) -> Dict[str, Dict]:
    """Everything wrong right now, keyed so the key survives from run to run."""
    from sqlalchemy import func
    from core.models import CouncilHealth, Article, LogEvent, RunSummary

    findings: Dict[str, Dict] = {}
    since = now - timedelta(hours=window_hours)

    # 1. Councils the breaker has switched off.
    for c in session.query(CouncilHealth).filter(CouncilHealth.is_disabled.is_(True)).all():
        if enabled is not None and c.council_id not in enabled:
            continue
        if (c.consecutive_failures or 0) >= DISABLE_FAILURES:
            why = f"{c.consecutive_failures} errors in a row"
        else:
            why = f"{c.consecutive_empty_runs or 0} empty scrapes in a row"
        findings[f"disabled:{c.council_id}"] = {
            "msg": f"{c.council_id} switched off by the circuit breaker ({why})",
            "ok": f"{c.council_id} is back on",
            "critical": False,
        }

    # 2. Proxy / auth failures.
    rows = session.query(LogEvent.message, func.count(LogEvent.id)).filter(
        LogEvent.created_at >= since,
        LogEvent.severity.in_(["error", "warning"]),
    ).group_by(LogEvent.message).all()
    hits = sorted(((m, n) for m, n in rows if m and INFRA_PATTERN.search(m)), key=lambda x: -x[1])
    if hits:
        top = "; ".join(f"{m[:60]} (x{n})" for m, n in hits[:3])
        findings["infra"] = {
            "msg": f"Proxy or Bluesky login failures in the last {window_hours:.0f}h: {top}",
            "ok": "No proxy or Bluesky login failures",
            "critical": True,
        }

    # 3. Missed scrape runs. councils_scraped > 0 leaves out the post-only
    #    queue runs, which would otherwise hide a dead scraper.
    run_counts = {
        (st or "").lower(): n for st, n in
        session.query(RunSummary.state, func.count(RunSummary.id))
        .filter(RunSummary.started_at >= now - timedelta(hours=24),
                RunSummary.councils_scraped > 0)
        .group_by(RunSummary.state).all()
    }
    no_runs = [st for st in ALL_STATES if run_counts.get(st, 0) == 0]
    if len(no_runs) == len(ALL_STATES):
        findings["missed_runs:ALL"] = {
            "msg": "No scrape runs in 24h for any state: cron or docker is dead, "
                   "or the crontab lost its scrape lines",
            "ok": "Scrape runs are happening again",
            "critical": True,
        }
    else:
        for st in no_runs:
            findings[f"missed_runs:{st.upper()}"] = {
                "msg": f"No scrape runs in 24h for {st.upper()}",
                "ok": f"{st.upper()} scrape runs are happening again",
                "critical": False,
            }

    # 4. Stalled queue: old queued work but nothing posting. An empty backlog
    #    going quiet is normal.
    stall_cutoff = now - timedelta(hours=2)
    pending_old = session.query(func.count(Article.id)).filter(
        Article.posted_at.is_(None),
        Article.status == 'new',
        Article.first_seen_at <= stall_cutoff,
    ).scalar() or 0
    last_post = session.query(func.max(Article.posted_at)).scalar()
    if pending_old and (last_post is None or last_post < stall_cutoff):
        last_str = last_post.strftime('%Y-%m-%d %H:%M UTC') if last_post else 'never'
        findings["queue_stalled"] = {
            "msg": f"Posting queue stalled: articles queued over 2h but nothing "
                   f"posted since {last_str}. Check the queue processor",
            "ok": "Posting queue is moving again",
            "critical": True,
        }

    return findings


def build_message(opened: Dict[str, Dict], cleared: Dict[str, Dict], still_open: int,
                  first_report: bool, mass_disable: int, now: datetime) -> Optional[Dict]:
    """One Discord embed for what changed, or None if nothing did."""
    if not opened and not cleared:
        return None
    newly_disabled = [k for k in opened if k.startswith("disabled:")]
    mass = len(newly_disabled) >= mass_disable
    critical = mass or any(f.get("critical") for f in opened.values())

    lines = []
    for key in sorted(opened):
        icon = "🔴" if opened[key].get("critical") or (mass and key in newly_disabled) else "⚠️"
        lines.append(f"{icon} {opened[key]['msg']}")
    for key in sorted(cleared):
        lines.append(f"✅ {cleared[key].get('ok') or 'Cleared: ' + cleared[key]['msg']}")
    if still_open:
        lines.append(f"\n{still_open} earlier problem(s) still open, not repeated.")

    if first_report:
        title = "Alert check: problems open now (first report; from here on, changes only)"
    elif mass:
        title = f"🔴 Mass disable: {len(newly_disabled)} councils switched off at once"
    elif critical:
        title = "🔴 New system problem"
    elif opened:
        title = "⚠️ New problem"
    else:
        title = "✅ Problem cleared"
    return {
        "title": title,
        "description": "\n".join(lines)[:4000],
        "color": RED if critical else ORANGE if opened else GREEN,
        "timestamp": now.isoformat(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-hours", type=float, default=6.0,
                    help="how far back to look for proxy/auth failures (default 6)")
    ap.add_argument("--mass-disable", type=int, default=5,
                    help="escalate if at least this many councils are switched off at once (default 5)")
    ap.add_argument("--dry-run", action="store_true", help="print only: send nothing, save nothing")
    args = ap.parse_args()

    from core.database import Database
    from core.monitor_state import load_state, save_state, diff_findings

    db = Database()
    now = datetime.utcnow()
    with db.get_session() as s:
        current = collect_findings(s, now, args.window_hours, enabled_council_ids())

    saved = load_state(db, STATE_KEY)
    previous = (saved or {}).get("findings", {})
    opened, cleared = diff_findings(previous, current)
    still_open = len(set(current) & set(previous))

    print(f"Alert check {now.strftime('%Y-%m-%d %H:%M UTC')}: {len(current)} open, "
          f"{len(opened)} opened, {len(cleared)} cleared")
    for f in current.values():
        print(f"  open: {f['msg']}")

    embed = build_message(opened, cleared, still_open, saved is None, args.mass_disable, now)
    if args.dry_run:
        if embed:
            print("Would send:\n" + json.dumps(embed, indent=1, ensure_ascii=False))
        return

    if embed:
        from discord_logger import send_discord_embed, DISCORD_WEBHOOK_ALERTS
        if not send_discord_embed(DISCORD_WEBHOOK_ALERTS, embed):
            print("Discord did not accept the alert; state not saved, will retry next run.")
            sys.exit(1)
        print("Sent: " + embed["title"])
    if embed or saved is None:
        save_state(db, STATE_KEY, {"findings": current, "at": now.isoformat()})


def _crash_alert(exc: Exception) -> None:
    """Last-ditch, DB-independent alert that the monitor itself died."""
    try:
        from discord_logger import send_discord_embed, DISCORD_WEBHOOK_ALERTS
        send_discord_embed(DISCORD_WEBHOOK_ALERTS, {
            "title": "🔴 alert_check CRASHED",
            "description": f"The alert monitor itself failed; alerting is blind until fixed.\n"
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
        print(f"alert_check crashed: {type(e).__name__}: {e}")
        _crash_alert(e)
        sys.exit(2)

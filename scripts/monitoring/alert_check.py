#!/usr/bin/env python3
"""
Alert check — the failure-mode detector (quiet-by-default).

Replaces the noisy hourly heartbeat. This runs on a schedule but speaks ONLY
when something is actually wrong, pushing a single consolidated alert to
DISCORD_WEBHOOK_ALERTS. It detects the failure modes that have silently slipped
past before:

  1. CIRCUIT BREAKER TRIPS — councils auto-disabled in the last window
     (the ~Apr-16 mass-disable of 85 councils was invisible). Escalates if many
     trip at once.
  2. STATE POSTED 0 — a state with no posts in the recent window (catches
     pipeline breaks like the validator crash fast).
  3. PROXY / AUTH FAILURES — proxy 402s or BlueSky auth failures recorded in
     log_events (the proxy lapse was silent for ~10 days).
  4. EMPTY-RUN COUNCILS — councils repeatedly returning 0 articles (the most
     common breakage; the old failures-only check missed it).

Pairs with feed_watchdog.py (which watches BlueSky output). This one watches the
internal state (DB). Read-only. Degrades gracefully without Discord.

Usage:
    python3 scripts/monitoring/alert_check.py
    python3 scripts/monitoring/alert_check.py --window-hours 6 --empty-threshold 5
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RED = 15158332
ORANGE = 15105570


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-hours", type=float, default=6.0,
                    help="how far back to look for trips / zero-post states (default 6)")
    ap.add_argument("--empty-threshold", type=int, default=5,
                    help="alert on councils with this many consecutive empty runs (default 5)")
    ap.add_argument("--mass-disable", type=int, default=5,
                    help="escalate if at least this many councils trip in the window (default 5)")
    args = ap.parse_args()

    from sqlalchemy import func
    from core.database import Database
    from core.models import CouncilHealth, Article, LogEvent

    db = Database()
    now = datetime.utcnow()
    since = now - timedelta(hours=args.window_hours)
    alerts = []

    with db.get_session() as s:
        # 1. Circuit-breaker trips in the window.
        tripped = s.query(CouncilHealth).filter(
            CouncilHealth.is_disabled.is_(True),
            CouncilHealth.disabled_at.isnot(None),
            CouncilHealth.disabled_at >= since,
        ).all()
        if tripped:
            ids = [c.council_id for c in tripped]
            sev = "🔴 MASS DISABLE" if len(ids) >= args.mass_disable else "⚠️ Disabled"
            shown = ", ".join(ids[:15]) + (f" (+{len(ids) - 15} more)" if len(ids) > 15 else "")
            alerts.append((len(ids) >= args.mass_disable,
                           f"**{sev}**: {len(ids)} council(s) auto-disabled in last "
                           f"{args.window_hours:.0f}h — {shown}"))

        # 2. States that posted 0 over a LONGER window. Posting is paced by the
        #    queue and can legitimately be quiet for hours overnight, so use a
        #    12h floor here to avoid crying wolf during normal lulls. A
        #    normally-busy state silent for 12h, or 3+ states silent at once
        #    (broad pipeline break), is a real problem.
        zero_window = max(args.window_hours, 12.0)
        zsince = now - timedelta(hours=zero_window)
        # articles.state is stored upper-case (e.g. "NSW") — normalise both sides.
        posted_states = {
            (st or "").lower(): n for st, n in
            s.query(Article.state, func.count(Article.id))
            .filter(Article.posted_at.isnot(None), Article.posted_at >= zsince)
            .group_by(Article.state).all()
        }
        all_states = ["nsw", "vic", "qld", "wa", "sa", "tas", "nt", "act"]
        silent = [st for st in all_states if posted_states.get(st, 0) == 0]
        busy_silent = [st for st in silent if st in ("nsw", "vic", "qld", "wa", "sa")]
        if len(silent) >= 3 or busy_silent:
            alerts.append((len(silent) >= 3,
                           f"**No posts**: {', '.join(s.upper() for s in silent)} posted nothing "
                           f"in last {zero_window:.0f}h"))

        # 3. Proxy / auth failures in log_events.
        infra = s.query(LogEvent.message, func.count(LogEvent.id)).filter(
            LogEvent.created_at >= since,
            LogEvent.severity.in_(["error", "warning"]),
        ).group_by(LogEvent.message).all()
        infra_hits = [(m, n) for (m, n) in infra
                      if m and any(k in m.lower() for k in
                                   ["402", "payment required", "proxy", "auth", "login", "unauthorized"])]
        if infra_hits:
            top = "; ".join(f"{m[:60]} (×{n})" for m, n in sorted(infra_hits, key=lambda x: -x[1])[:3])
            alerts.append((True, f"**Infra failure** (proxy/auth): {top}"))

        # 4. Councils with high empty-run counts (still enabled).
        empties = s.query(CouncilHealth).filter(
            CouncilHealth.is_disabled.is_(False),
            CouncilHealth.consecutive_empty_runs >= args.empty_threshold,
        ).order_by(CouncilHealth.consecutive_empty_runs.desc()).all()
        if empties:
            shown = ", ".join(f"{c.council_id}({c.consecutive_empty_runs})" for c in empties[:12])
            extra = f" (+{len(empties) - 12} more)" if len(empties) > 12 else ""
            alerts.append((False,
                           f"**Empty runs** (≥{args.empty_threshold}): {len(empties)} council(s) "
                           f"scraping nothing — {shown}{extra}"))

    print(f"Alert check — {now.strftime('%Y-%m-%d %H:%M UTC')} (window {args.window_hours:.0f}h)")
    if not alerts:
        print("  ✅ Nothing to alert.")
        return

    critical = any(c for c, _ in alerts)
    body = "\n".join(f"• {msg}" for _, msg in alerts)
    print("ALERTS:\n" + body)
    try:
        from discord_logger import send_discord_embed, DISCORD_WEBHOOK_ALERTS
        send_discord_embed(DISCORD_WEBHOOK_ALERTS, {
            "title": "🔴 System alert" if critical else "⚠️ System notices",
            "description": body[:4000],
            "color": RED if critical else ORANGE,
            "timestamp": now.isoformat(),
        })
    except Exception as e:
        print(f"(Discord alert not sent: {e})")
    sys.exit(1)


if __name__ == "__main__":
    main()

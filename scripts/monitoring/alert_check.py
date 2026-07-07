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
  5. MISSED SCRAPE RUNS — a state with no run_summaries rows in 24h (wedged
     cron/docker or a bad crontab install). Backlog can keep feeds looking
     alive for days while scraping is dead.
  6. STALLED QUEUE — articles queued for hours while nothing posts (queue
     processor death, distinct from scrape death).

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
    from core.models import CouncilHealth, Article, LogEvent, RunSummary

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

        # 5. Missed scrape runs: staggered scraping gives every state ~6 runs
        #    per 24h; zero rows means cron/docker is wedged or a crontab
        #    install dropped the scrape lines.
        run_counts = {
            (st or "").lower(): n for st, n in
            s.query(RunSummary.state, func.count(RunSummary.id))
            .filter(RunSummary.started_at >= now - timedelta(hours=24))
            .group_by(RunSummary.state).all()
        }
        no_runs = [st for st in all_states if run_counts.get(st, 0) == 0]
        if len(no_runs) == len(all_states):
            alerts.append((True,
                           "**No scrape runs in 24h for ANY state** — cron/docker is dead "
                           "or the crontab lost its scrape lines"))
        elif no_runs:
            alerts.append((len(no_runs) >= 3,
                           f"**Missed scrape runs**: no runs in 24h for "
                           f"{', '.join(st.upper() for st in no_runs)}"))

        # 6. Stalled queue: only alert when there IS old queued work but
        #    nothing has posted — an empty backlog going quiet is normal.
        stall_cutoff = now - timedelta(hours=2)
        pending_old = s.query(func.count(Article.id)).filter(
            Article.posted_at.is_(None),
            Article.status == 'new',
            Article.first_seen_at <= stall_cutoff,
        ).scalar() or 0
        last_post = s.query(func.max(Article.posted_at)).scalar()
        if pending_old and (last_post is None or last_post < stall_cutoff):
            last_str = last_post.strftime('%Y-%m-%d %H:%M UTC') if last_post else 'never'
            alerts.append((True,
                           f"**Queue stalled**: {pending_old} article(s) queued >2h but "
                           f"nothing posted since {last_str} — check the queue processor"))

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


def _crash_alert(exc: Exception) -> None:
    """Last-ditch, DB-independent alert that the monitor itself died."""
    try:
        from discord_logger import send_discord_embed, DISCORD_WEBHOOK_ALERTS
        send_discord_embed(DISCORD_WEBHOOK_ALERTS, {
            "title": "🔴 alert_check CRASHED",
            "description": f"The alert monitor itself failed — alerting is blind until fixed.\n"
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

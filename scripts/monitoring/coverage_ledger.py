#!/usr/bin/env python3
"""Coverage ledger: the weekly answer to "is every council being relayed?"

The circuit breaker, the briefings and the health scripts all measure "did
the scraper run and find items". That is the wrong question. In the 2 Nov
2026 audit, City of Sydney passed every one of those checks and had posted
nothing for months, because its page served 2021-2023 articles; twelve more
councils were "healthy" while archiving everything they found; and 17 had
been switched off by the breaker with nobody keeping a list.

This script sorts every configured council into one bucket, by OUTPUT:

  posting      posted at least once in the window
  quiet        healthy, found nothing new, and not overdue by its own history
  overdue      healthy, found nothing new, but silent for more than twice its
               usual gap between posts (something changed on that site)
  stale_only   healthy and finding items, but none posted: everything it finds
               is archived on arrival or rejected (wrong page, bad selectors)
  broken_error disabled by the breaker after consecutive fetch errors
  broken_empty disabled by the breaker after consecutive empty runs
  never_scraped in config but no health row

and prints the honest coverage number: posting councils as a share of the
councils that are not merely quiet. With --discord it posts the same table
to the logs webhook; with --json it writes the full ledger for the website.
"""
import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

WINDOW_DAYS = 30
BASELINE_DAYS = 180
BUCKETS = ("posting", "quiet", "overdue", "stale_only", "broken_error", "broken_empty", "never_scraped")
BROKEN = ("broken_error", "broken_empty")


def load_councils(states_dir: Path) -> Dict[str, Dict]:
    """Enabled councils from states/*/councils.json, keyed by id."""
    out: Dict[str, Dict] = {}
    for path in sorted(states_dir.glob("*/councils.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        councils = raw["councils"] if isinstance(raw, dict) else raw
        for c in councils:
            if not c.get("enabled", True):
                continue
            out[c["id"]] = {
                "id": c["id"], "name": c["name"], "state": path.parent.name.upper(),
                "population": c.get("population"),
            }
    return out


def classify(health: Optional[Dict], facts: Dict, now: datetime, window_days: int = WINDOW_DAYS) -> Tuple[str, str]:
    """Pure decision. `facts` carries the per-council article aggregates.

    Returns (bucket, one-line detail)."""
    if health is None:
        return "never_scraped", "no health row"
    if health.get("is_disabled"):
        if (health.get("consecutive_failures") or 0) > 0:
            return "broken_error", (f"{health['consecutive_failures']} consecutive errors, "
                                    f"last ok {_d(health.get('last_success_at'))}")
        return "broken_empty", (f"{health.get('consecutive_empty_runs') or 0} consecutive empty runs, "
                                f"last article {_d(facts.get('last_seen'))}")
    if facts.get("posted_window", 0) > 0:
        return "posting", f"{facts['posted_window']} posted"
    if facts.get("seen_window", 0) > 0:
        return "stale_only", (f"{facts['seen_window']} found, {facts.get('archived_window', 0)} archived on arrival, "
                              f"{facts.get('rejected_window', 0)} rejected; last post {_d(facts.get('last_posted'))}")
    gap = facts.get("median_gap_days")
    last_posted = facts.get("last_posted")
    if gap and last_posted:
        silent = (now - last_posted).days
        if silent > max(2 * gap, window_days):
            return "overdue", f"silent {silent}d, usual gap {gap:.0f}d"
    return "quiet", f"nothing new; last post {_d(last_posted)}"


def _d(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d") if dt else "never"


def build_facts(db, now: datetime, window_days: int = WINDOW_DAYS,
                baseline_days: int = BASELINE_DAYS) -> Dict[str, Dict]:
    """Per-council article aggregates from the database."""
    from sqlalchemy import func
    from core.models import Article

    since = now - timedelta(days=window_days)
    baseline_since = now - timedelta(days=baseline_days)
    facts: Dict[str, Dict] = defaultdict(dict)
    with db.get_session() as s:
        rows = s.query(
            Article.council_id,
            func.count(Article.id).filter(Article.first_seen_at >= since),
            func.count(Article.id).filter(Article.status == "posted", Article.posted_at >= since),
            func.count(Article.id).filter(Article.status == "archived", Article.first_seen_at >= since),
            func.count(Article.id).filter(Article.status == "rejected", Article.first_seen_at >= since),
            func.max(Article.first_seen_at),
        ).group_by(Article.council_id).all()
        for cid, seen, posted, archived, rejected, last_seen in rows:
            facts[cid].update(seen_window=seen, posted_window=posted, archived_window=archived,
                              rejected_window=rejected, last_seen=last_seen)
        for cid, last_posted in s.query(Article.council_id, func.max(Article.posted_at)) \
                .filter(Article.status == "posted").group_by(Article.council_id).all():
            facts[cid]["last_posted"] = last_posted
        stamps: Dict[str, List[datetime]] = defaultdict(list)
        for cid, posted_at in s.query(Article.council_id, Article.posted_at) \
                .filter(Article.status == "posted", Article.posted_at >= baseline_since).all():
            stamps[cid].append(posted_at)
    for cid, ts in stamps.items():
        facts[cid]["median_gap_days"] = median_gap_days(ts)
    return facts


def median_gap_days(stamps: Iterable[datetime]) -> Optional[float]:
    """Median gap between a council's posting days (same-day posts count once)."""
    days = sorted({t.date() for t in stamps})
    if len(days) < 3:
        return None
    gaps = [(b - a).days for a, b in zip(days, days[1:])]
    return float(statistics.median(gaps))


def load_health(db) -> Dict[str, Dict]:
    from core.models import CouncilHealth
    with db.get_session() as s:
        return {h.council_id: {
            "consecutive_failures": h.consecutive_failures, "consecutive_empty_runs": h.consecutive_empty_runs,
            "is_disabled": h.is_disabled, "disabled_at": h.disabled_at,
            "last_success_at": h.last_success_at, "last_failure_at": h.last_failure_at,
        } for h in s.query(CouncilHealth).all()}


def build_ledger(councils: Dict[str, Dict], health: Dict[str, Dict], facts: Dict[str, Dict],
                 now: datetime, window_days: int = WINDOW_DAYS) -> Dict:
    rows = []
    for cid, c in councils.items():
        bucket, detail = classify(health.get(cid), facts.get(cid, {}), now, window_days)
        rows.append({**c, "bucket": bucket, "detail": detail})
    counts = Counter(r["bucket"] for r in rows)
    not_quiet = len(rows) - counts["quiet"]
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "window_days": window_days,
        "configured": len(rows),
        "counts": {b: counts.get(b, 0) for b in BUCKETS},
        "active_coverage": round(100.0 * counts["posting"] / not_quiet, 1) if not_quiet else None,
        "rows": sorted(rows, key=lambda r: (BUCKETS.index(r["bucket"]), r["state"], r["name"])),
        "orphan_health_rows": sorted(set(health) - set(councils)),
    }


def render(ledger: Dict, limit: int = 40) -> str:
    c = ledger["counts"]
    lines = [
        f"Coverage ledger {ledger['generated_at'][:10]} ({ledger['window_days']}-day window)",
        (f"configured {ledger['configured']} | posting {c['posting']} | quiet {c['quiet']} | overdue {c['overdue']} | "
         f"stale-only {c['stale_only']} | broken {c['broken_error'] + c['broken_empty']} "
         f"(error {c['broken_error']}, empty {c['broken_empty']}) | never scraped {c['never_scraped']}"),
        f"Active coverage: {ledger['active_coverage']}% of councils that are not merely quiet",
        "",
    ]
    for bucket in ("broken_error", "broken_empty", "stale_only", "overdue", "never_scraped"):
        rows = [r for r in ledger["rows"] if r["bucket"] == bucket]
        if not rows:
            continue
        lines.append(f"{bucket.replace('_', ' ').upper()} ({len(rows)})")
        for r in rows[:limit]:
            lines.append(f"  {r['state']:4}{r['name'][:38]:40}{r['detail']}")
        if len(rows) > limit:
            lines.append(f"  ... and {len(rows) - limit} more")
        lines.append("")
    if ledger["orphan_health_rows"]:
        lines.append(f"Health rows with no enabled config ({len(ledger['orphan_health_rows'])}): "
                     + ", ".join(ledger["orphan_health_rows"]))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--window-days", type=int, default=WINDOW_DAYS)
    ap.add_argument("--states-dir", type=Path, default=ROOT / "states")
    ap.add_argument("--json", type=Path, help="write the full ledger here")
    ap.add_argument("--discord", action="store_true", help="post the summary to DISCORD_WEBHOOK_LOGS")
    ap.add_argument("--fail-on-broken", action="store_true", help="exit 1 if any council is broken or stale-only")
    args = ap.parse_args()

    from core.database import Database
    db = Database()
    now = datetime.utcnow()
    councils = load_councils(args.states_dir)
    ledger = build_ledger(councils, load_health(db), build_facts(db, now, args.window_days), now, args.window_days)
    text = render(ledger)
    print(text)
    if args.json:
        args.json.write_text(json.dumps(ledger, default=str, indent=1), encoding="utf-8")
    if args.discord:
        try:
            from discord_logger import send_discord_embed, DISCORD_WEBHOOK_LOGS
            send_discord_embed(DISCORD_WEBHOOK_LOGS, {
                "title": "📒 Weekly coverage ledger",
                "description": "```\n" + text[:3900] + "\n```",
                "color": 3447003,
                "timestamp": now.isoformat(),
            })
        except Exception as e:  # the ledger itself must never fail because Discord did
            print(f"(Discord not sent: {e})")
    c = ledger["counts"]
    if args.fail_on_broken and (c["broken_error"] + c["broken_empty"] + c["stale_only"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

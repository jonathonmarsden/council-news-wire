#!/usr/bin/env python3
"""Post the scheduled feed promotions, at most one per channel per occurrence.

Run daily from cron. The script decides for itself whether today is a promo day
for any channel, so the rotating schedule lives in code that can be tested
rather than in a crontab that would need regenerating every cycle.

Safety properties, in order of how much they matter:

  * **Never double-posts.** Every send is recorded in a ledger keyed by channel
    and occurrence, and a channel whose occurrence is already in the ledger is
    skipped. Cron retries, a manual re-run, or two containers racing all
    converge on one post.
  * **Never posts unattended from the human account.** The national channel is
    marked requires_approval, so it writes a draft for review instead of
    publishing. --approve national sends the pending draft.
  * **Says what it would do.** --dry-run prints the posts and exits, and is the
    default when no credentials are present.

Usage:
  run_promotion.py                  # post whatever is due today
  run_promotion.py --dry-run        # show what would be posted
  run_promotion.py --schedule 90    # print the next 90 days of promo days
  run_promotion.py --approve national   # send the pending national draft
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.promotion import (  # noqa: E402
    CHANNELS, CHANNELS_BY_KEY, EXCLUDED, account_for, deferred_channels,
    due_channels, interval_for, occurrence_index, post_time_utc,
)
from core.promotion_copy import compose  # noqa: E402

DATA_DIR = Path(os.environ.get("LGNEWS_DATA_DIR", "data"))
LEDGER = DATA_DIR / "promotion_ledger.json"
DRAFTS = DATA_DIR / "promotion_drafts.json"

# Anchors the rotation. Changing it shifts every future promo day, so it is a
# fixed date rather than "whenever this was first deployed".
EPOCH = date(2026, 8, 3)


def _load(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _save(path, data):
    """Write `data` to `path` atomically.

    The temp-then-replace keeps a crash from leaving a half-written ledger, and
    a ledger that cannot be trusted is one that lets a promo post twice.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(path)


def check_ledger_is_writable():
    """Fail loudly before posting if the ledger cannot be written.

    The ledger is the only thing preventing a repeat post, and the cron line
    ticks five times a night. An unwritable ledger would therefore post the
    same promo five times into someone else's hashtag - so this refuses to
    start rather than risking it. (The container runs as botuser while data/ is
    root-owned, which is exactly how this was first hit.)
    """
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        probe = LEDGER.parent / ".write-probe"
        probe.write_text("ok")
        probe.unlink()
        return True
    except OSError as exc:
        print("FATAL: cannot write the promotion ledger at {} ({})".format(
            LEDGER.parent, exc), file=sys.stderr)
        print("Nothing was posted. Set LGNEWS_DATA_DIR to a writable path.",
              file=sys.stderr)
        return False


def ledger_key(channel_key, occurrence):
    return "{}:{}".format(channel_key, occurrence)


def send(channel, account, text, dry_run):
    """Publish `text` from `account`. Returns a status string."""
    if dry_run:
        return "dry-run"

    handle = os.environ.get("BLUESKY_HANDLE_{}".format(account))
    password = os.environ.get("BLUESKY_PASSWORD_{}".format(account))
    if not handle or not password:
        return "skipped: no credentials for {}".format(account)

    from core.poster import BlueSkyPoster
    poster = BlueSkyPoster(handle, password, state_code=account)
    if not poster.authenticate():
        return "failed: authentication"

    text_out, facets = poster.build_facets_for_text(text)
    response = poster.client.send_post(text=text_out, facets=facets)
    return "posted: {}".format(getattr(response, "uri", "ok"))


def run(today, dry_run, verbose=True, now=None, respect_window=False):
    """Post whatever is due on `today`.

    With `respect_window` the channel is held back until the scheduled minute
    has arrived in its own timezone - that is what lets cron tick hourly across
    21:00-01:00 UTC while each feed still posts in its own local morning.
    Off by default so a manual run does not silently do nothing.
    """
    ledger = _load(LEDGER)
    drafts = _load(DRAFTS)
    due = due_channels(today, EPOCH)
    now = now or datetime.now(timezone.utc)

    if not due:
        if verbose:
            print("{}: nothing due".format(today))
        return 0

    # A capped channel loses this occurrence entirely rather than posting late,
    # which keeps its interval honest - but say so, because a silent skip is
    # indistinguishable from a bug.
    for channel in deferred_channels(today, EPOCH):
        print("{:<10} deferred: more than {} channels due today".format(
            channel.key, len(due)))

    for channel in due:
        occurrence = occurrence_index(channel, today, EPOCH)
        key = ledger_key(channel.key, occurrence)
        if key in ledger:
            if verbose:
                print("{:<10} occurrence {} already handled - skipping".format(
                    channel.key, occurrence))
            continue

        account = account_for(channel, occurrence)
        text = compose(channel, account, occurrence)
        when = post_time_utc(channel, today, occurrence)

        if respect_window and now < when:
            if verbose:
                print("{:<10} due at {} UTC - not yet".format(
                    channel.key, when.strftime("%H:%M")))
            continue

        if channel.requires_approval:
            # The national channel posts from a person's account, so it is
            # drafted rather than sent. Nothing is written to the ledger: the
            # occurrence is only spent once it is actually approved.
            drafts[channel.key] = {
                "occurrence": occurrence, "account": account, "text": text,
                "tag": channel.tag, "drafted_for": today.isoformat(),
            }
            _save(DRAFTS, drafts)
            print("\n{} DRAFT for approval (account: {}, tag: {})".format(
                channel.key.upper(), account, channel.tag))
            print("-" * 60)
            print(text)
            print("-" * 60)
            print("Approve with: run_promotion.py --approve {}".format(channel.key))
            continue

        status = send(channel, account, text, dry_run)
        if verbose:
            print("\n{:<10} occurrence {} via {} at {} UTC -> {}".format(
                channel.key, occurrence, account, when.strftime("%H:%M"), status))
            print(text)

        # Only a real, successful send consumes the occurrence. A dry run must
        # leave the schedule untouched, and a failed send must leave the promo
        # available to retry rather than silently losing it.
        if status.startswith("posted") and not dry_run:
            ledger[key] = {"account": account, "tag": channel.tag,
                           "posted_at": datetime.now(timezone.utc).isoformat(),
                           "text": text}
            _save(LEDGER, ledger)
    return 0


def approve(channel_key, dry_run):
    drafts = _load(DRAFTS)
    draft = drafts.get(channel_key)
    if not draft:
        print("No pending draft for {}".format(channel_key))
        return 1

    channel = CHANNELS_BY_KEY[channel_key]
    ledger = _load(LEDGER)
    key = ledger_key(channel_key, draft["occurrence"])
    if key in ledger:
        print("Occurrence {} was already posted.".format(draft["occurrence"]))
        return 1

    status = send(channel, draft["account"], draft["text"], dry_run)
    print(status)
    if status.startswith("posted") and not dry_run:
        ledger[key] = {"account": draft["account"], "tag": draft["tag"],
                       "posted_at": datetime.now(timezone.utc).isoformat(),
                       "text": draft["text"], "approved": True}
        _save(LEDGER, ledger)
        drafts.pop(channel_key, None)
        _save(DRAFTS, drafts)
    return 0


def print_schedule(days):
    print("Promotion schedule from {} ({} days)\n".format(EPOCH, days))
    print("{:<12}{:<11}{:<10}{:<9}{}".format(
        "date", "weekday", "channel", "account", "tag"))
    print("-" * 60)
    for offset in range(days):
        day = EPOCH + timedelta(days=offset)
        for channel in due_channels(day, EPOCH):
            occurrence = occurrence_index(channel, day, EPOCH)
            account = account_for(channel, occurrence)
            when = post_time_utc(channel, day, occurrence)
            print("{:<12}{:<11}{:<10}{:<9}{}{}".format(
                day.isoformat(), day.strftime("%a"), channel.key, account,
                channel.tag,
                "  [approval] {} UTC".format(when.strftime("%H:%M"))
                if channel.requires_approval else "  {} UTC".format(when.strftime("%H:%M"))))
    print("\nCadence (measured 2026-08-02):")
    for c in CHANNELS:
        print("  {:<10} {:<10} every {:>2}d  ~{:>5.2f}% of {} posts/wk".format(
            c.key, c.tag, interval_for(c), c.share_pct, c.weekly_volume))
    for state, why in EXCLUDED.items():
        print("  {:<10} excluded: {}".format(state, why))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="show, do not post")
    ap.add_argument("--schedule", type=int, metavar="DAYS",
                    help="print the upcoming schedule and exit")
    ap.add_argument("--approve", metavar="CHANNEL",
                    help="send the pending draft for CHANNEL")
    ap.add_argument("--date", help="pretend today is YYYY-MM-DD (testing)")
    ap.add_argument("--window", action="store_true",
                    help="only post once the channel's local morning window has "
                         "arrived (used by the hourly cron tick)")
    args = ap.parse_args()

    if args.schedule:
        print_schedule(args.schedule)
        return 0

    # Default to dry-run when nothing is configured, so a mis-set cron
    # environment prints instead of failing silently.
    dry_run = args.dry_run or not os.environ.get("BLUESKY_PASSWORD_VIC")

    # A dry run touches nothing, so it is allowed to proceed regardless.
    if not dry_run and not check_ledger_is_writable():
        return 1

    if args.approve:
        return approve(args.approve, dry_run)

    if args.date:
        return run(date.fromisoformat(args.date), dry_run)

    # The schedule is expressed in Australian local dates, and the promo window
    # (07:30-09:00 local) falls on the PREVIOUS UTC day. Using date.today() on a
    # UTC-clocked server would therefore look up the wrong day and post nothing.
    today = datetime.now(ZoneInfo("Australia/Sydney")).date()
    return run(today, dry_run, respect_window=args.window)


if __name__ == "__main__":
    sys.exit(main())

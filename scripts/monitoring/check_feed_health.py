#!/usr/bin/env python3
"""
Daily health check for the LG News network: 8 Bluesky state feeds + website.

For each state account it verifies, via Bluesky's public AppView (no auth):
  1. the profile is publicly visible (catches suspensions, takedowns and the
     stale `handle.invalid` AppView state that silently hid WA in July 2026);
  2. the newest post is younger than --stale-hours (catches silent posting
     failures: auth breakage, dead cron, a downed server).

The website check requires an HTTP 200 from the public URL.

Exit code is 0 when everything is healthy, 1 otherwise — so a scheduler
(GitHub Actions, cron + mail) can alert on failure with no extra logic.

If NTFY_URL is set (e.g. http://ntfy.example:8080/lgnews), a summary is pushed
there on every run — green or red. Run it daily and treat the *absence* of the
morning message as an alert in itself: a monitor that only speaks up on
failure cannot report the failure of its own host.

Usage:
  check_feed_health.py                     # check, print, exit 0/1
  NTFY_URL=http://host:8080/topic check_feed_health.py
  check_feed_health.py --stale-hours 48
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

STATES = ["vic", "nsw", "qld", "sa", "wa", "tas", "nt", "act"]
HANDLE = "roundupnewsbot{}.bsky.social"
APPVIEW = "https://public.api.bsky.app/xrpc"
WEBSITE = "https://lgnews.jonathonmarsden.com/"
TIMEOUT = 15


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lgnews-monitor/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)


def check_feed(state, stale_hours):
    """Return (ok: bool, detail: str) for one state account."""
    handle = HANDLE.format(state)
    url = "{}/app.bsky.feed.getAuthorFeed?{}".format(
        APPVIEW, urllib.parse.urlencode({"actor": handle, "limit": 1})
    )
    try:
        data = fetch_json(url)
    except urllib.error.HTTPError as e:
        # 400 "Profile not found" is how the AppView reports a hidden account
        return False, "profile not publicly visible (HTTP {})".format(e.code)
    except Exception as e:
        return False, "unreachable: {}".format(e)

    feed = data.get("feed", [])
    if not feed:
        return False, "no posts returned"

    created = feed[0]["post"]["record"].get("createdAt", "")
    try:
        ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    except ValueError:
        return False, "unparseable post timestamp: {!r}".format(created)

    if age_h > stale_hours:
        return False, "silent for {:.0f}h (limit {}h)".format(age_h, stale_hours)
    return True, "last post {:.1f}h ago".format(age_h)


def check_website():
    req = urllib.request.Request(WEBSITE, headers={"User-Agent": "lgnews-monitor/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            if resp.status == 200:
                return True, "HTTP 200"
            return False, "HTTP {}".format(resp.status)
    except Exception as e:
        return False, "unreachable: {}".format(e)


def push_ntfy(ntfy_url, healthy, lines):
    title = "LG News: all healthy" if healthy else "LG News: PROBLEMS"
    body = "\n".join(lines)
    headers = {
        "Title": title,
        "Priority": "default" if healthy else "high",
    }
    token = os.environ.get("NTFY_TOKEN")
    if token:
        headers["Authorization"] = "Bearer {}".format(token)
    req = urllib.request.Request(ntfy_url, data=body.encode(), headers=headers)
    try:
        urllib.request.urlopen(req, timeout=TIMEOUT).read()
    except Exception as e:
        # Never let a notification failure mask the health result itself
        print("warning: ntfy push failed: {}".format(e), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--stale-hours", type=float, default=48,
                        help="max hours since a feed's newest post (default 48)")
    args = parser.parse_args()

    lines, healthy = [], True
    for state in STATES:
        ok, detail = check_feed(state, args.stale_hours)
        healthy &= ok
        lines.append("{} {}: {}".format("OK " if ok else "FAIL", state.upper(), detail))
    ok, detail = check_website()
    healthy &= ok
    lines.append("{} site: {}".format("OK " if ok else "FAIL", detail))

    print("\n".join(lines))
    ntfy_url = os.environ.get("NTFY_URL")
    if ntfy_url:
        push_ntfy(ntfy_url, healthy, lines)
    sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    main()

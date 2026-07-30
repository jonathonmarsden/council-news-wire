#!/usr/bin/env python3
"""Shortlist posts worth amplifying into a large community such as #Auspol.

Why this is not simply "post the day's most-liked story": across the eight
feeds, 240 recent posts carried 13 likes between them. Ranking by engagement
at that level is ranking noise, and an automated daily push of a randomly
chosen council notice into a 10,000-post-a-month tag is the exact behaviour
that annoys a community and trips spam heuristics.

So this tool *suggests*, and a person chooses. It scores recent posts on
engagement where any exists, and otherwise on editorial signal - the subjects
people actually respond to (budgets, rates, planning, closures, elections,
safety) - and prints a shortlist with ready-to-use quote-post links.

As the feeds grow, engagement naturally starts to dominate the score and the
same tool becomes the engagement-ranked amplifier it was meant to be, with no
change needed.

Usage:
    amplify_candidates.py                 # top 5 from the last 24h
    amplify_candidates.py --hours 48 --top 8
    amplify_candidates.py --json          # machine-readable
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

STATES = ["vic", "nsw", "qld", "sa", "wa", "tas", "nt", "act"]
APPVIEW = "https://public.api.bsky.app/xrpc"

# Subjects that reliably interest a general political audience. Weighted so a
# rates or budget story outranks a library opening when nothing has any likes.
TOPIC_WEIGHTS = [
    (r"\brate(s|payer)", 5), (r"\bbudget", 5), (r"\belection|\bpoll", 4),
    (r"\bplanning|\brezon|\bdevelopment application|\bDA\b", 4),
    (r"\bclos(ing|ure|ed)|\bcancel", 3), (r"\bsafety|\bflood|\bfire|\bemergency", 4),
    (r"\bhousing|\bhomeless", 5), (r"\bconsultation|\bhave your say|\bfeedback", 3),
    (r"\bcouncillor|\bmayor|\bCEO\b|\bresign", 4),
    (r"\broad|\bfootpath|\btransport|\bparking", 2),
    (r"\bclimate|\benvironment|\bwaste|\brecycl", 3),
    (r"\bfund(ing|ed)|\bgrant|\b\$[0-9]", 3),
]
# Routine notices that rarely reward amplification.
NEGATIVE = [(r"\bminutes\b|\bagenda\b|\bnotice of meeting", -6),
            (r"\bpublic notice\b", -3), (r"\blibrary hours|\bopening hours", -2)]


def fetch(url):
    return json.load(urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "lgnews-amplify/1.0"}),
        timeout=25))


def topic_score(text: str) -> int:
    score = 0
    for pattern, weight in TOPIC_WEIGHTS + NEGATIVE:
        if re.search(pattern, text, re.IGNORECASE):
            score += weight
    return score


def post_url(uri: str, handle: str) -> str:
    return f"https://bsky.app/profile/{handle}/post/{uri.split('/')[-1]}"


def gather(hours: int):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for st in STATES:
        handle = f"roundupnewsbot{st}.bsky.social"
        try:
            data = fetch(f"{APPVIEW}/app.bsky.feed.getAuthorFeed"
                         f"?actor={handle}&limit=60")
        except Exception as e:
            print(f"warning: {st} feed unavailable: {e}", file=sys.stderr)
            continue
        for item in data.get("feed", []):
            post = item["post"]
            rec = post.get("record", {})
            created = rec.get("createdAt", "")
            try:
                ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                continue
            if ts < cutoff:
                continue
            text = rec.get("text", "")
            first_line = text.split("\n")[0]
            if first_line.startswith("Every story from"):
                continue  # the pinned post
            likes = post.get("likeCount", 0)
            reposts = post.get("repostCount", 0)
            quotes = post.get("quoteCount", 0)
            replies = post.get("replyCount", 0)
            engagement = likes + 3 * reposts + 3 * quotes + 2 * replies
            out.append({
                "state": st.upper(),
                "title": first_line,
                "url": post_url(post["uri"], handle),
                "likes": likes, "reposts": reposts,
                # Engagement is weighted heavily so it dominates as soon as it
                # exists; topic signal only breaks ties in a silent feed.
                "score": engagement * 10 + topic_score(text),
                "engagement": engagement,
                "has_card": bool(post.get("embed")),
            })
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = sorted(gather(args.hours), key=lambda r: -r["score"])[:args.top]
    if args.json:
        print(json.dumps(rows, indent=1))
        return

    if not rows:
        print(f"No posts in the last {args.hours}h.")
        return
    print(f"Amplification shortlist - last {args.hours}h, top {len(rows)}\n")
    for i, r in enumerate(rows, 1):
        flag = f"{r['likes']}L/{r['reposts']}R" if r["engagement"] else "no engagement yet"
        print(f"{i}. [{r['state']}] {r['title'][:64]}")
        print(f"   score {r['score']:>3} ({flag}){'  [card]' if r['has_card'] else ''}")
        print(f"   {r['url']}\n")
    print("Pick one, quote-post it from the personal account with a line of "
          "human comment, and add #Auspol there - not on the feed posts.")


if __name__ == "__main__":
    main()

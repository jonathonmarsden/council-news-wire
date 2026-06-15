#!/usr/bin/env python3
"""
Coverage & health triage — find silently-broken council scrapers.

The lighter, high-signal variant (see docs/SCRAPER_REPAIR_PLAYBOOK.md):
  1. Tally which enabled councils actually appear in recent BlueSky posts.
  2. Live-scrape ONLY the absent councils and classify each.
  3. Reconcile: confirmed-broken = absent from deep feed AND scrapes JUNK/DEAD.

Run from the repo root:
    python3 scripts/maintenance/triage_coverage.py            # all states
    python3 scripts/maintenance/triage_coverage.py --state nsw

Outputs a per-state table and writes the confirmed-broken set to
docs/broken_councils.json. Local IP may be WAF/Cloudflare-blocked for some
sites, so a council marked broken here should be confirmed on the VPS
(docker compose exec -T -w /app bot ...) before deep fixing.
"""
import argparse
import io
import json
import logging
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HANDLES = {
    "vic": "roundupnewsbotvic.bsky.social", "nsw": "roundupnewsbotnsw.bsky.social",
    "qld": "roundupnewsbotqld.bsky.social", "sa": "roundupnewsbotsa.bsky.social",
    "wa": "roundupnewsbotwa.bsky.social", "tas": "roundupnewsbottas.bsky.social",
    "nt": "roundupnewsbotnt.bsky.social", "act": "roundupnewsbotact.bsky.social",
}
API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
FRESH = timedelta(days=7)
SUFFIXES = ["regional council", "shire council", "city council", "municipal council",
            "district council", "town council", "aboriginal shire", "council", "shire",
            "city of", "the ", "regional", "municipality of", "borough of", "district"]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def shortkey(name):
    n = (name or "").lower()
    for w in SUFFIXES:
        n = n.replace(w, " ")
    return norm(n)


def deep_pull(handle, rounds=8):
    posts, cursor = [], None
    for _ in range(rounds):
        url = f"{API}?actor={handle}&limit=100" + (f"&cursor={cursor}" if cursor else "")
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
        except Exception:
            break
        posts += data.get("feed", [])
        cursor = data.get("cursor")
        if not cursor:
            break
        time.sleep(0.25)
    return posts


def represented(handle, councils):
    text = " ".join(norm(p["post"]["record"].get("text", "")) for p in deep_pull(handle))
    seen = set()
    for c in councils:
        full, short = norm(c["name"]), shortkey(c["name"])
        if (len(full) > 6 and full in text) or (len(short) >= 5 and short in text):
            seen.add(c["id"])
    return seen


def classify(cfg):
    from core.scrapers.factory import ScraperFactory
    from core.validator import is_valid_article
    now = datetime.now(timezone.utc)
    try:
        old = sys.stdout
        sys.stdout = io.StringIO()
        arts = ScraperFactory.create_scraper(cfg).scrape()
        sys.stdout = old
    except Exception as e:
        return {"id": cfg["id"], "cls": "DEAD", "detail": type(e).__name__}
    valid = [a for a in arts if is_valid_article(a)]
    dated = [a for a in valid if getattr(a, "date", None)]

    def aware(d):
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    fresh = [a for a in dated if (now - aware(a.date)) <= FRESH]
    if not arts:
        cls = "DEAD"
    elif not valid or not dated:
        cls = "JUNK"
    elif fresh:
        cls = "HEALTHY"
    else:
        cls = "STALE"
    return {"id": cfg["id"], "cls": cls, "n": len(arts), "valid": len(valid)}


def main():
    logging.disable(logging.CRITICAL)
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", help="single state (e.g. nsw)")
    args = ap.parse_args()
    states = [args.state.lower()] if args.state else list(HANDLES)

    confirmed = {}
    print(f"{'ST':4}{'enabled':>9}{'in feed':>9}{'absent':>8}{'->JUNK/DEAD':>13}")
    for st in states:
        councils = [c for c in json.load(open(ROOT / f"states/{st}/councils.json"))["councils"]
                    if c.get("enabled")]
        seen = represented(HANDLES[st], councils)
        absent = [c for c in councils if c["id"] not in seen]
        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(classify, absent))
        broken = [r["id"] for r in results if r["cls"] in ("JUNK", "DEAD")]
        if broken:
            confirmed[st.upper()] = sorted(broken)
        print(f"{st.upper():4}{len(councils):>9}{len(seen):>9}{len(absent):>8}{len(broken):>13}")

    out = ROOT / "docs" / "broken_councils.json"
    json.dump(confirmed, open(out, "w"), indent=2)
    total = sum(len(v) for v in confirmed.values())
    print(f"\n{total} confirmed broken (absent from feed + scrapes JUNK/DEAD). Wrote {out}")
    print("Confirm on the VPS before deep fixing — local IP may be WAF-blocked.")


if __name__ == "__main__":
    main()

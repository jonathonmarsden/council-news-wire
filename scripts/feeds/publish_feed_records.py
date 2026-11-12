#!/usr/bin/env python3
"""Publish (or update) the Bluesky feed records for every feed in config/feeds.json.

A Bluesky custom feed is a record (app.bsky.feed.generator) in the repository
of the account that offers it, pointing at the feed generator service. This
writes one record per feed, keyed by the feed id, so running it again updates
names and descriptions in place. It never touches posts.

Run it from a machine that holds the publishing account's app password:

    FEEDS_HANDLE="yourproject.bsky.social" FEEDS_APP_PASSWORD="your-app-password" \\
        python3 scripts/feeds/publish_feed_records.py            # dry run: lists what it would write
        python3 scripts/feeds/publish_feed_records.py --write    # writes the records

It prints the account's DID, which the edge service needs as PUBLISHER_DID.
--prune also deletes feed records on the account that are no longer in the
config (use when a feed is retired).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION = "app.bsky.feed.generator"
DEFAULT_SERVICE_DID = "did:web:councilnewswire.au"


def records(service_did: str, created_at: str):
    feeds = json.loads((ROOT / "config/feeds.json").read_text(encoding="utf-8"))["feeds"]
    for f in feeds:
        yield f["id"], {
            "$type": COLLECTION,
            "did": service_did,
            "displayName": f["name"],
            "description": f["description"],
            "createdAt": created_at,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="actually write the records (default: dry run)")
    ap.add_argument("--prune", action="store_true", help="delete feed records not in config (needs --write)")
    ap.add_argument("--service-did", default=os.environ.get("FEEDS_SERVICE_DID", DEFAULT_SERVICE_DID))
    args = ap.parse_args()

    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    wanted = dict(records(args.service_did, created))
    if not args.write:
        for rkey, rec in wanted.items():
            print(f"{rkey:16} {rec['displayName']!r}  ({len(rec['description'])} chars)")
        print(f"\n{len(wanted)} feed records -> service {args.service_did}. Dry run; add --write to publish.")
        return 0

    handle, password = os.environ.get("FEEDS_HANDLE"), os.environ.get("FEEDS_APP_PASSWORD")
    if not handle or not password:
        print("Set FEEDS_HANDLE and FEEDS_APP_PASSWORD (an app password, not the account password).", file=sys.stderr)
        return 2
    from atproto import Client
    client = Client()
    client.login(handle, password)
    did = client.me.did

    existing = {}
    cursor = None
    while True:
        page = client.com.atproto.repo.list_records({"repo": did, "collection": COLLECTION, "limit": 100, "cursor": cursor})
        for r in page.records:
            existing[r.uri.rsplit("/", 1)[-1]] = r.value
        cursor = page.cursor
        if not cursor:
            break

    for rkey, rec in wanted.items():
        old = existing.get(rkey)
        if old is not None and getattr(old, "created_at", None):
            rec["createdAt"] = old.created_at  # keep the original creation time
        client.com.atproto.repo.put_record({"repo": did, "collection": COLLECTION, "rkey": rkey, "record": rec})
        print(f"{'updated' if old is not None else 'created'} {rkey}")

    if args.prune:
        for rkey in sorted(set(existing) - set(wanted)):
            client.com.atproto.repo.delete_record({"repo": did, "collection": COLLECTION, "rkey": rkey})
            print(f"deleted {rkey}")

    print(f"\nPublisher DID (set as PUBLISHER_DID on the edge service): {did}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

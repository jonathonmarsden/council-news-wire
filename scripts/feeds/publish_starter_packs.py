#!/usr/bin/env python3
"""Publish (or update) one Bluesky starter pack per state, from config/starter_packs.json.

A starter pack is a share link that follows a set of accounts and saves up to
three custom feeds in one tap; people who sign up through it get them during
onboarding. Each state's pack holds that state's news account, the shared
accounts in the config (the podcast and the feeds account) and three of the
state's region feeds.

Each pack is three kinds of record in the publishing account's repository: a
reference list (app.bsky.graph.list), its members (app.bsky.graph.listitem)
and the pack itself (app.bsky.graph.starterpack). Records use fixed keys
(pack-<state> for the list, <state> for the pack), so running this again
updates names, descriptions, members and feeds in place.

    FEEDS_HANDLE="lgnews.jonathonmarsden.com" FEEDS_APP_PASSWORD="your-app-password" \\
        python3 scripts/feeds/publish_starter_packs.py           # dry run
        python3 scripts/feeds/publish_starter_packs.py --write   # publish

It prints each pack's share link.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = "lgnews.jonathonmarsden.com"
STATE_NAMES = {"nsw": "New South Wales", "vic": "Victoria", "qld": "Queensland", "wa": "Western Australia",
               "sa": "South Australia", "tas": "Tasmania", "nt": "the Northern Territory",
               "act": "the ACT"}
NAME_MAX, DESC_MAX = 50, 300


def load():
    cfg = json.loads((ROOT / "config/starter_packs.json").read_text(encoding="utf-8"))
    feeds = {f["id"]: f for f in json.loads((ROOT / "config/feeds.json").read_text(encoding="utf-8"))["feeds"]}
    return cfg, feeds


def state_handle(state: str) -> str:
    return f"roundupnewsbot{state}.bsky.social"


def describe(pack: dict, feeds: dict) -> str:
    st = pack["state"]
    names = [feeds[f]["name"] for f in pack["feeds"]]
    listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    total = sum(1 for f in feeds.values() if f["state"].lower() == st)
    tail = (f" All {total} {pack['adj']} region feeds, and RSS: {SITE}/{st}" if total > len(names)
            else f" RSS for every council: {SITE}/{st}")
    return (f"Council news from across {STATE_NAMES[st]} as it's published, the LG News Roundup podcast, "
            f"and region feeds for {listed}.{tail}")


def plan(cfg: dict, feeds: dict):
    """(state, name, description, member handles, feed ids) for each pack, validated."""
    out = []
    for p in cfg["packs"]:
        desc = describe(p, feeds)
        if len(p["name"]) > NAME_MAX or len(desc) > DESC_MAX:
            raise ValueError(f"{p['state']}: name or description too long ({len(p['name'])}, {len(desc)})")
        if not 1 <= len(p["feeds"]) <= 3 or any(f not in feeds for f in p["feeds"]):
            raise ValueError(f"{p['state']}: needs 1-3 known feed ids, got {p['feeds']}")
        out.append((p["state"], p["name"], desc, [state_handle(p["state"])] + cfg["accounts"], p["feeds"]))
    return out


def list_records(client, did: str, collection: str):
    cursor = None
    while True:
        page = client.com.atproto.repo.list_records({"repo": did, "collection": collection, "limit": 100, "cursor": cursor})
        yield from page.records
        cursor = page.cursor
        if not cursor:
            return


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="actually publish (default: dry run)")
    args = ap.parse_args()

    cfg, feeds = load()
    packs = plan(cfg, feeds)
    if not args.write:
        for st, name, desc, members, feed_ids in packs:
            print(f"{st}: {name!r}\n  {desc}\n  ({len(desc)} chars) members: {', '.join(members)}\n  feeds: {', '.join(feed_ids)}")
        print(f"\n{len(packs)} packs. Dry run; add --write to publish.")
        return 0

    handle, password = os.environ.get("FEEDS_HANDLE"), os.environ.get("FEEDS_APP_PASSWORD")
    if not handle or not password:
        print("Set FEEDS_HANDLE and FEEDS_APP_PASSWORD (an app password, not the account password).", file=sys.stderr)
        return 2
    from atproto import Client
    client = Client()
    client.login(handle, password)
    did = client.me.did
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    dids = {}
    for _, _, _, members, _ in packs:
        for h in members:
            if h not in dids:
                dids[h] = client.com.atproto.identity.resolve_handle({"handle": h}).did

    lists = {r.uri.rsplit("/", 1)[-1]: r for r in list_records(client, did, "app.bsky.graph.list")}
    packs_old = {r.uri.rsplit("/", 1)[-1]: r for r in list_records(client, did, "app.bsky.graph.starterpack")}
    items = list(list_records(client, did, "app.bsky.graph.listitem"))

    def created(old):
        return getattr(old.value, "created_at", None) if old is not None else None

    for st, name, desc, members, feed_ids in packs:
        list_rkey = f"pack-{st}"
        list_uri = f"at://{did}/app.bsky.graph.list/{list_rkey}"
        client.com.atproto.repo.put_record({"repo": did, "collection": "app.bsky.graph.list", "rkey": list_rkey, "record": {
            "$type": "app.bsky.graph.list", "purpose": "app.bsky.graph.defs#referencelist",
            "name": name, "createdAt": created(lists.get(list_rkey)) or now}})

        have = {i.value.subject: i for i in items if i.value.list == list_uri}
        want = {dids[h] for h in members}
        for subject in want - set(have):
            client.com.atproto.repo.create_record({"repo": did, "collection": "app.bsky.graph.listitem", "record": {
                "$type": "app.bsky.graph.listitem", "subject": subject, "list": list_uri, "createdAt": now}})
        for subject in set(have) - want:
            client.com.atproto.repo.delete_record({"repo": did, "collection": "app.bsky.graph.listitem",
                                                   "rkey": have[subject].uri.rsplit("/", 1)[-1]})

        client.com.atproto.repo.put_record({"repo": did, "collection": "app.bsky.graph.starterpack", "rkey": st, "record": {
            "$type": "app.bsky.graph.starterpack", "name": name, "description": desc, "list": list_uri,
            "feeds": [{"uri": f"at://{did}/app.bsky.feed.generator/{f}"} for f in feed_ids],
            "createdAt": created(packs_old.get(st)) or now}})
        print(f"{'updated' if st in packs_old else 'created'} {name}: https://bsky.app/starter-pack/{handle}/{st}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

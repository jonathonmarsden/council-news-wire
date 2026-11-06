"""The per-state starter packs stay valid against Bluesky's limits and the feeds config."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "publish_starter_packs", Path(__file__).resolve().parents[1] / "scripts/feeds/publish_starter_packs.py")
psp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(psp)


def test_every_state_has_one_valid_pack():
    cfg, feeds = psp.load()
    packs = psp.plan(cfg, feeds)  # raises on over-long text or unknown feeds
    assert sorted(p[0] for p in packs) == sorted(psp.STATE_NAMES)
    for st, name, desc, members, feed_ids in packs:
        assert members[0] == f"roundupnewsbot{st}.bsky.social"
        # Only feeds from the pack's own state, except the ACT's NSW neighbours.
        assert all(feeds[f]["state"].lower() == st or st == "act" for f in feed_ids), st


def test_record_keys_are_valid_unique_tids():
    import re
    keys = [psp.record_key(st, k) for st in psp.STATE_ORDER for k in ("list", "pack")]
    assert len(set(keys)) == len(keys)
    for k in keys:  # atproto TID syntax
        assert re.fullmatch(r"[234567abcdefghij][234567abcdefghijklmnopqrstuvwxyz]{12}", k), k
    assert sorted(psp.STATE_ORDER) == sorted(psp.STATE_NAMES)

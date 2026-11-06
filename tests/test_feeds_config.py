"""The region feeds config stays consistent with the council configs.

config/feeds.json defines one Bluesky custom feed per group of councils.
A feed that names a council id that has been renamed or switched off would
silently lose that council's stories, and a newly added council that is in no
feed would be invisible to anyone following feeds rather than state accounts.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEEDS = json.loads((ROOT / "config/feeds.json").read_text(encoding="utf-8"))["feeds"]

# Councils deliberately in no region feed, with the reason.
NO_FEED = {
    "cocos-keeling-islands": "no region; an Indian Ocean Territory",
}


def _councils():
    out = {}
    for path in sorted(ROOT.glob("states/*/councils.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for c in raw["councils"] if isinstance(raw, dict) else raw:
            out[c["id"]] = {**c, "_state": path.parent.name}
    return out


COUNCILS = _councils()
ENABLED = {cid for cid, c in COUNCILS.items() if c.get("enabled", True)}


def test_ids_are_unique_short_slugs():
    ids = [f["id"] for f in FEEDS]
    assert len(ids) == len(set(ids))
    for fid in ids:
        assert re.fullmatch(r"[a-z0-9-]{1,15}", fid), fid


def test_names_and_descriptions_fit_bluesky_limits():
    for f in FEEDS:
        assert 0 < len(f["name"]) <= 24, f["name"]
        assert 0 < len(f["description"]) <= 300, f["id"]


def test_every_member_is_a_configured_enabled_council():
    for f in FEEDS:
        assert f["council_ids"], f["id"]
        unknown = [c for c in f["council_ids"] if c not in COUNCILS]
        disabled = [c for c in f["council_ids"] if c in COUNCILS and c not in ENABLED]
        assert not unknown, (f["id"], unknown)
        assert not disabled, (f["id"], disabled)


def test_every_enabled_council_is_in_at_least_one_feed():
    in_a_feed = {c for f in FEEDS for c in f["council_ids"]}
    missing = sorted(ENABLED - in_a_feed - set(NO_FEED))
    assert not missing, f"enabled councils in no feed: {missing}"


def test_every_wa_council_has_a_region():
    # WA regions were added with the feeds; keep them complete.
    missing = [cid for cid, c in COUNCILS.items()
               if c["_state"] == "wa" and c.get("enabled", True) and not c.get("region")]
    assert not missing, missing


def test_descriptions_do_not_repeat_a_name():
    # The ACT has several news sources with the same name; listing each one
    # made the Canberra feed read "ACT Government, ACT Government, ...".
    for f in FEEDS:
        parts = [p.strip() for p in re.split(r"[:,.]| and ", f["description"]) if p.strip()]
        dupes = {p for p in parts if parts.count(p) > 1}
        assert not dupes, (f["id"], dupes)

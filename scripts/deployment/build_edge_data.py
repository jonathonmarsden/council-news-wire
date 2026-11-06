#!/usr/bin/env python3
"""Write edge/src/data.json: the feeds and councils the edge service serves.

The edge Worker cannot read the repo at run time, so it is deployed with a
snapshot of config/feeds.json and of every enabled council (id, name, state,
news page). Run this after changing either, then redeploy the Worker.
tests/test_edge_data.py fails while the snapshot is out of date.

    python3 scripts/deployment/build_edge_data.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "edge" / "src" / "data.json"


def build() -> dict:
    councils = {}
    for path in sorted(ROOT.glob("states/*/councils.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for c in raw["councils"] if isinstance(raw, dict) else raw:
            if c.get("enabled", True):
                councils[c["id"]] = {"id": c["id"], "name": c["name"],
                                     "state": path.parent.name, "news_url": c["news_url"]}
    feeds = json.loads((ROOT / "config" / "feeds.json").read_text(encoding="utf-8"))["feeds"]
    keep = ("id", "name", "state", "kind", "description", "council_ids")
    return {"feeds": [{k: f[k] for k in keep} for f in feeds],
            "councils": dict(sorted(councils.items()))}


def render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    OUT.write_text(render(build()), encoding="utf-8")
    d = build()
    print(f"wrote {OUT.relative_to(ROOT)}: {len(d['feeds'])} feeds, {len(d['councils'])} councils", file=sys.stderr)

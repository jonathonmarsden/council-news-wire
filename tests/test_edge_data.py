"""The edge Worker's data snapshot matches the repo's feeds and councils.

The Worker is deployed with edge/src/data.json because it cannot read the repo.
If a council is added or a feed changes without regenerating it, RSS and the
Bluesky feeds silently serve the old membership.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_edge_data", ROOT / "scripts/deployment/build_edge_data.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_snapshot_is_current():
    current = (ROOT / "edge/src/data.json").read_text(encoding="utf-8")
    assert current == mod.render(mod.build()), (
        "edge/src/data.json is stale: run python3 scripts/deployment/build_edge_data.py")

import json
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HEALTH_REPORT_PATH = PROJECT_ROOT / "HEALTH_REPORT_FROM_VPS.md"
STATES_DIR = PROJECT_ROOT / "states"


def load_dead_council_names() -> list[str]:
    """Parse HEALTH_REPORT_FROM_VPS.md dead-scrapers table and return council names.

    Looks for the markdown table under the heading
    "## ❌ Dead Scrapers (Never found articles)" and extracts the
    second column (Council name) from each row:

        | State | Council | URL |
        | NSW   | Dubbo Regional Council | https://... |
    """
    if not HEALTH_REPORT_PATH.exists():
        raise SystemExit(f"Missing {HEALTH_REPORT_PATH}. Copy it from the VPS first.")

    text = HEALTH_REPORT_PATH.read_text(encoding="utf-8")

    # Find the dead-scrapers section
    m = re.search(r"^## .*Dead Scrapers[\s\S]*?^\| State \| Council \| URL \ |",
                  text, re.MULTILINE)
    if not m:
        raise SystemExit("Could not find dead scrapers table in health report")

    # Start from the header line
    start = m.start()
    tail = text[start:].splitlines()

    # Skip header and separator
    rows = []
    started = False
    for line in tail:
        if not started:
            if line.strip().startswith("| State | Council | URL |"):
                started = True
            continue
        # Stop when we hit an empty line or next heading
        if not line.strip() or line.lstrip().startswith("## "):
            break
        if not line.strip().startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 3:
            continue
        # parts should be [State, Council, URL]
        rows.append(parts[1])

    return rows


def load_state_configs() -> dict[str, dict]:
    """Load `states/*/councils.json` into a mapping of council_id -> metadata.

    Also build a secondary index from council *name* to id so we can
    map names in the health report back to ids.
    """
    mapping: dict[str, dict] = {}
    name_index: dict[str, str] = {}
    for state_dir in STATES_DIR.iterdir():
        if not state_dir.is_dir():
            continue
        cfile = state_dir / "councils.json"
        if not cfile.exists():
            continue
        data = json.loads(cfile.read_text(encoding="utf-8"))
        for council in data.get("councils", []):
            cid = council.get("id")
            name = council.get("name")
            if not cid or not name:
                continue
            mapping[cid] = {
                "state": state_dir.name,
                "name": name,
                "scraper": council.get("scraper"),
                "has_selectors": any(k.endswith("_selector") for k in council.keys()),
                "has_rss_url": bool(council.get("rss_url")),
                "category": council.get("category"),
                "note": council.get("note"),
            }
            # Use lower-cased name as key for simple matching
            name_index[name.lower()] = cid

    # Attach the name index so callers can use it
    mapping["__name_index__"] = name_index
    return mapping


def main() -> None:
    dead_names = load_dead_council_names()
    config_map = load_state_configs()
    name_index = config_map.pop("__name_index__", {})

    lines = [
        "# Dead Scrapers Pattern Report",
        "",
        "council_id,state,scraper,has_selectors,has_rss_url,category,note",
    ]

    resolved_ids: list[str] = []
    for name in dead_names:
        cid = name_index.get(name.lower())
        if not cid:
            # Skip if we cannot map the name back to an id
            continue
        resolved_ids.append(cid)
        meta = config_map.get(cid, {})
        lines.append(
            ",".join(
                [
                    cid,
                    meta.get("state", ""),
                    (meta.get("scraper") or ""),
                    "yes" if meta.get("has_selectors") else "no",
                    "yes" if meta.get("has_rss_url") else "no",
                    (meta.get("category") or ""),
                    (meta.get("note") or ""),
                ]
            )
        )

    out_path = PROJECT_ROOT / "docs" / "reports" / "DEAD_SCRAPERS_PATTERN_REPORT.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path} with {len(resolved_ids)} dead councils (from {len(dead_names)} names)")


if __name__ == "__main__":
    main()

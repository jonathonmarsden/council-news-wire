"""The edge sync sends each posted story in the shape the edge accepts."""
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sync_edge", ROOT / "scripts/cron/sync_edge.py")
se = importlib.util.module_from_spec(spec)
spec.loader.exec_module(se)


def art(**kw):
    base = dict(url="https://council.example/news/1", title=" Roads closed ", council_id="brisbane", state="QLD",
                excerpt=None, og_description="From the card", bluesky_uri="at://did:plc:x/app.bsky.feed.post/1",
                date=datetime(2026, 11, 5, 0, 0), posted_at=datetime(2026, 11, 5, 2, 30))
    base.update(kw)
    return SimpleNamespace(**base)


def test_payload_fields():
    p = se.to_payload(art(), {"brisbane": "Brisbane City Council"})
    assert p["state"] == "qld"
    assert p["title"] == "Roads closed"
    assert p["council_name"] == "Brisbane City Council"
    assert p["excerpt"] == "From the card"  # falls back to the link-card description
    assert p["posted_at"] == "2026-11-05T02:30:00Z"  # stored in UTC


def test_council_dates_are_read_as_australian_local_time():
    # Midnight 5 Nov in Sydney (AEDT, +11) is 13:00 on 4 Nov UTC.
    assert se.to_payload(art(), {})["published_at"] == "2026-11-04T13:00:00Z"


def test_rows_missing_essentials_are_skipped():
    assert se.to_payload(art(title=None), {}) is None
    assert se.to_payload(art(posted_at=None), {}) is None


def test_iso_utc_keeps_aware_datetimes():
    assert se.iso_utc(datetime(2026, 1, 1, tzinfo=timezone.utc)) == "2026-01-01T00:00:00Z"
    assert se.iso_utc(None) is None


def test_batches_split_evenly():
    assert [len(b) for b in se.batches(list(range(900)), 400)] == [400, 400, 100]

"""Alerts report changes, not conditions.

Before this, alert_check posted on every run for weeks: the same "empty runs"
notice four times a day, plus a fresh "auto-disabled" notice every three days
for each broken council as its probation retry failed. The feed watchdog's
repeat suppression never worked, because its message carried an hour count
that changed every run. A channel that repeats itself is a channel nobody
reads. These tests pin the replacement: a problem is reported when it opens
and when it clears, and never in between.
"""
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

from core.models import Article, CouncilHealth, RunSummary
from core.monitor_state import diff_findings, load_state, save_state

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/monitoring/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ac = _load("alert_check")
fw = _load("feed_watchdog")
NOW = datetime(2026, 11, 5, 12, 0)


def _healthy_runs(s):
    """A scrape run for every state, so missed_runs does not fire."""
    for i, st in enumerate(ac.ALL_STATES):
        s.add(RunSummary(run_id=f"r{i}", state=st.upper(), started_at=NOW - timedelta(hours=1),
                         ended_at=NOW, duration_ms=1, councils_scraped=3))


# ---- the diff ----------------------------------------------------------------

def test_diff_reports_only_opened_and_cleared():
    prev = {"a": {"msg": "A"}, "b": {"msg": "B"}}
    cur = {"b": {"msg": "B"}, "c": {"msg": "C"}}
    opened, cleared = diff_findings(prev, cur)
    assert set(opened) == {"c"} and set(cleared) == {"a"}


def test_state_round_trips(db):
    assert load_state(db, "x") is None
    save_state(db, "x", {"findings": {"k": {"msg": "m"}}})
    save_state(db, "x", {"findings": {}})
    assert load_state(db, "x") == {"findings": {}}


# ---- alert_check findings ------------------------------------------------------

def test_disabled_council_found_once_and_probation_does_not_change_the_key(db):
    with db.get_session() as s:
        _healthy_runs(s)
        s.add(CouncilHealth(council_id="dubbo", is_disabled=True, consecutive_failures=10,
                            consecutive_empty_runs=0, disabled_at=NOW))
        s.commit()
        first = ac.collect_findings(s, NOW, 6)
    # A failed probation re-stamps disabled_at; the finding must be unchanged.
    db.record_failure("dubbo")
    with db.get_session() as s:
        second = ac.collect_findings(s, NOW, 6)
    assert set(first) == set(second) == {"disabled:dubbo"}
    assert "errors in a row" in first["disabled:dubbo"]["msg"]


def test_councils_not_enabled_in_config_are_ignored(db):
    with db.get_session() as s:
        _healthy_runs(s)
        s.add(CouncilHealth(council_id="removed", is_disabled=True, consecutive_failures=5,
                            consecutive_empty_runs=0))
        s.commit()
        assert ac.collect_findings(s, NOW, 6, enabled={"dubbo"}) == {}


def test_empty_runs_below_the_breaker_are_not_a_finding(db):
    with db.get_session() as s:
        _healthy_runs(s)
        s.add(CouncilHealth(council_id="richmond", is_disabled=False, consecutive_failures=0,
                            consecutive_empty_runs=12))
        s.commit()
        assert ac.collect_findings(s, NOW, 6) == {}


def test_no_runs_anywhere_is_one_critical_finding(db):
    with db.get_session() as s:
        f = ac.collect_findings(s, NOW, 6)
    assert set(f) == {"missed_runs:ALL"} and f["missed_runs:ALL"]["critical"]


def test_stalled_queue(db):
    with db.get_session() as s:
        _healthy_runs(s)
        s.add(Article(url="u1", title="t", council_id="c", state="NSW", status="new",
                      first_seen_at=NOW - timedelta(hours=5)))
        s.add(Article(url="u2", title="t", council_id="c", state="NSW", status="posted",
                      posted_at=NOW - timedelta(hours=4)))
        s.commit()
        assert "queue_stalled" in ac.collect_findings(s, NOW, 6)


def test_infra_pattern_ignores_words_that_merely_contain_auth():
    assert ac.INFRA_PATTERN.search("ProxyError: 402 Payment Required")
    assert ac.INFRA_PATTERN.search("Bluesky login failed: Invalid identifier or password")
    assert not ac.INFRA_PATTERN.search("Scraper error: 404 at /news/water-authority-update")
    assert not ac.INFRA_PATTERN.search("Unhandled scraper exception: author field missing")


# ---- alert_check message -------------------------------------------------------

def test_nothing_changed_sends_nothing():
    assert ac.build_message({}, {}, 3, False, 5, NOW) is None


def test_cleared_only_is_green_and_says_back_on():
    m = ac.build_message({}, {"disabled:x": {"msg": "x off", "ok": "x is back on"}}, 0, False, 5, NOW)
    assert m["color"] == ac.GREEN and "x is back on" in m["description"]


def test_many_switched_off_at_once_escalates():
    opened = {f"disabled:c{i}": {"msg": f"c{i} off", "critical": False} for i in range(7)}
    m = ac.build_message(opened, {}, 0, False, 5, NOW)
    assert m["color"] == ac.RED and "Mass disable" in m["title"]


def test_still_open_count_is_mentioned_not_repeated():
    m = ac.build_message({"queue_stalled": {"msg": "stalled", "critical": True}}, {}, 2, False, 5, NOW)
    assert "2 earlier problem(s) still open" in m["description"]


# ---- feed_watchdog -------------------------------------------------------------

def test_watchdog_finding_keys_carry_no_changing_numbers(monkeypatch):
    feed = [{"post": {"indexedAt": "2026-11-05T10:00:00Z", "record": {"text": "Nothing local"}}}]
    monkeypatch.setattr(fw, "pull", lambda handle, depth: (feed, None))
    findings, _ = fw.check(0.20, 1)
    # Big states are thin (no council named); keys are just the state.
    assert "thin:NSW" in findings and all(k.count(":") == 1 for k in findings)
    # Single-council ACT is never judged on coverage.
    assert "thin:ACT" not in findings


def test_unreadable_feed_is_not_a_finding(monkeypatch):
    monkeypatch.setattr(fw, "pull", lambda handle, depth: ([], "timed out"))
    findings, lines = fw.check(0.20, 1)
    assert findings == {} and all("could not read" in ln for ln in lines)

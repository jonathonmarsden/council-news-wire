"""Tests for per-feed staleness thresholds in the health monitor.

A single 48-hour threshold fired on ACT about a third of the time while
nothing was wrong: across its last 38 posting intervals, 12 exceeded 48 hours
and the longest ran to weeks. An alarm that cries wolf is one you learn to
ignore, which is how a real outage gets missed - so the quiet feeds get their
own thresholds.
"""
import importlib.util
import pathlib

import pytest

spec = importlib.util.spec_from_file_location(
    "check_feed_health",
    pathlib.Path(__file__).parent.parent / "scripts" / "monitoring" / "check_feed_health.py")
cfh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfh)


def test_quiet_feeds_have_longer_thresholds():
    assert cfh.STALE_HOURS_BY_STATE["act"] > 48
    assert cfh.STALE_HOURS_BY_STATE["nt"] > 48


def test_busy_feeds_use_the_default():
    for state in ("vic", "nsw", "qld", "sa", "wa"):
        assert state not in cfh.STALE_HOURS_BY_STATE


def test_act_tolerates_a_normal_multi_day_gap():
    """64 hours of ACT silence is ordinary and must not alarm."""
    assert cfh.STALE_HOURS_BY_STATE["act"] > 64


def test_thresholds_are_not_so_long_that_an_outage_hides():
    """WA was invisible for nine days; nothing should exceed two weeks."""
    for state, hours in cfh.STALE_HOURS_BY_STATE.items():
        assert hours <= 14 * 24, f"{state} threshold would hide a real outage"

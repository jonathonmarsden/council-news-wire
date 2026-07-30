"""Tests for the routine-post hashtag set.

A 2026-07-30 survey found the tags then in use were almost entirely our own
output (#VLGA 100% self, #LGNSW 100%, #VicCouncils 96%, #MAV 92%), so five tags
per post bought no discovery. These tests pin the replacement: a small set of
tags with real external communities, and no #Auspol on routine posts - at this
posting volume that tag would be swamped.
"""
import pytest

from core.poster import BRAND_TAG, STATE_TAGS, tags_for_state


ALL_STATES = ["VIC", "NSW", "QLD", "SA", "WA", "TAS", "NT", "ACT"]


@pytest.mark.parametrize("state", ALL_STATES)
def test_every_state_has_a_small_tag_set(state):
    tags = tags_for_state(state)
    assert tags[0] == BRAND_TAG
    assert 2 <= len(tags) <= 4, f"{state} has {len(tags)} tags; keep posts uncluttered"
    assert len(set(tags)) == len(tags), "no duplicate tags"
    assert all(t.startswith("#") for t in tags)


@pytest.mark.parametrize("state", ALL_STATES)
def test_auspol_is_never_on_routine_posts(state):
    """#Auspol is reserved for curated amplification, not the firehose."""
    assert not any(t.lower() == "#auspol" for t in tags_for_state(state))


@pytest.mark.parametrize("state", ALL_STATES)
def test_self_generated_tags_are_dropped(state):
    """The tags the survey showed nobody outside this network reads."""
    dead = {"#vlga", "#mav", "#lgnsw", "#lgaq", "#lgasa", "#walga", "#lgat",
            "#lgant", "#alga", "#viccouncils", "#nswcouncils", "#qldcouncils",
            "#sacouncils", "#wacouncils", "#tascouncils", "#ntcouncils"}
    assert not (set(t.lower() for t in tags_for_state(state)) & dead)


def test_localgov_is_present_for_states():
    """The one real sector community that isn't ours."""
    for state in ALL_STATES:
        assert "#LocalGov" in tags_for_state(state)


def test_unknown_state_falls_back_to_national():
    assert tags_for_state("ZZZ") == tags_for_state("NAT")
    assert tags_for_state(None) == tags_for_state("NAT")


def test_env_override_replaces_state_tags(monkeypatch):
    monkeypatch.setenv("LGNEWS_TAGS_VIC", "#LocalGov,#Melbourne")
    assert tags_for_state("VIC") == [BRAND_TAG, "#LocalGov", "#Melbourne"]


def test_env_override_adds_missing_hash(monkeypatch):
    monkeypatch.setenv("LGNEWS_TAGS_VIC", "LocalGov, Melbourne")
    assert tags_for_state("VIC") == [BRAND_TAG, "#LocalGov", "#Melbourne"]


def test_empty_env_override_leaves_brand_tag_only(monkeypatch):
    monkeypatch.setenv("LGNEWS_TAGS_TAS", "")
    assert tags_for_state("TAS") == [BRAND_TAG]


def test_state_tags_table_covers_all_feeds():
    for state in ALL_STATES:
        assert state in STATE_TAGS, f"{state} missing from STATE_TAGS"

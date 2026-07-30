"""Tests for the routine-post hashtag set.

Policy: routine posts carry only tags this project owns - its own tag and the
council's. Community tags are excluded because of the arithmetic, not taste.
The network publishes ~8,000 posts a month against measured tag volumes of
#LocalGov 158/mo, #WApol 101, #SpringSt 256, #NSWpol 350, #Auspol 10,000. Using
them would make this feed 98%, 93%, 88%, 86% and 44% of those tags
respectively: not participating in a community, replacing it.

Community tags belong to curated amplification from the personal account, a
few posts a day (scripts/monitoring/amplify_candidates.py).
"""
import pytest

from core.poster import BRAND_TAG, STATE_TAGS, _is_own_tag, tags_for_state


ALL_STATES = ["VIC", "NSW", "QLD", "SA", "WA", "TAS", "NT", "ACT"]

# Tags owned by other people. None of these may appear on a routine post.
COMMUNITY_TAGS = {
    "#auspol", "#localgov", "#localnews", "#springst", "#nswpol", "#qldpol",
    "#wapol", "#politas", "#ntpol", "#actpol", "#adelaide", "#canberra",
    "#melbourne", "#sydney", "#brisbane", "#perth",
    # peak bodies - ours in spirit but read by no one, so still excluded
    "#vlga", "#mav", "#lgnsw", "#lgaq", "#lgasa", "#walga", "#lgat", "#lgant",
    "#alga", "#viccouncils", "#nswcouncils", "#qldcouncils", "#sacouncils",
    "#wacouncils", "#tascouncils", "#ntcouncils",
}


@pytest.mark.parametrize("state", ALL_STATES)
def test_routine_posts_carry_no_community_tags(state):
    tags = {t.lower() for t in tags_for_state(state)}
    assert not (tags & COMMUNITY_TAGS), (
        f"{state} would flood a tag it does not own")


@pytest.mark.parametrize("state", ALL_STATES)
def test_brand_tag_is_present(state):
    assert tags_for_state(state) == [BRAND_TAG]


def test_unknown_state_falls_back_to_national():
    assert tags_for_state("ZZZ") == tags_for_state("NAT") == [BRAND_TAG]
    assert tags_for_state(None) == [BRAND_TAG]


# --- ownership test, which decides what a stale config may re-introduce ----

def test_brand_tag_is_owned():
    assert _is_own_tag("#LGNewsRoundup")


@pytest.mark.parametrize("tag", ["#BathurstRegionalCouncil", "#MoyneShireCouncil",
                                 "#CityOfDarwin council", "#GlenelgShire"])
def test_council_tags_are_owned(tag):
    assert _is_own_tag(tag), f"{tag} should count as a council tag"


def test_council_tag_matches_by_name():
    assert _is_own_tag("#BathurstRegionalCouncil", "Bathurst Regional Council")


@pytest.mark.parametrize("tag", ["#Auspol", "#LocalGov", "#NSWpol", "#VLGA",
                                 "#NSWCouncils", "#Melbourne", "#housing"])
def test_community_tags_are_not_owned(tag):
    assert not _is_own_tag(tag), f"{tag} belongs to other people"


def test_empty_tag_is_not_owned():
    assert not _is_own_tag("")
    assert not _is_own_tag("#")


# --- env override ---------------------------------------------------------

def test_env_override_can_add_a_tag(monkeypatch):
    """The override exists so tagging can be retuned without a deploy."""
    monkeypatch.setenv("LGNEWS_TAGS_VIC", "#Melbourne")
    assert tags_for_state("VIC") == [BRAND_TAG, "#Melbourne"]


def test_empty_env_override_leaves_brand_tag_only(monkeypatch):
    monkeypatch.setenv("LGNEWS_TAGS_TAS", "")
    assert tags_for_state("TAS") == [BRAND_TAG]


def test_state_tags_table_covers_all_feeds():
    for state in ALL_STATES:
        assert state in STATE_TAGS, f"{state} missing from STATE_TAGS"

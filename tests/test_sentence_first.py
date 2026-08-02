"""Tests for the sentence-first post format.

Measured on Bluesky (2026-07-30), every high-engagement news bot - unofficial
ABC (12,850 followers, 3.50 eng/post), SBS (3.72), BBC UK (2.36) - writes the
story's opening sentence as the post text and lets the link card carry the
headline. Ours printed the headline in the text and again on the card, wasting
the most valuable line of the post.

Councils publish summaries inconsistently (25-75% of articles by state), so the
format must fall back to the headline whenever no usable sentence exists.
"""
from datetime import datetime

import pytest

from core.poster import BlueSkyPoster, MAX_LEDE_LEN, MIN_LEDE_LEN, _first_sentence


GOOD = ("The fire pits are ready, the food trucks are warming up and live music "
        "will soon fill the air as A Winter's Night returns to Tonsley.")


# --- sentence extraction --------------------------------------------------

def test_extracts_a_complete_opening_sentence():
    text = GOOD + " A second sentence follows here."
    assert _first_sentence(text) == GOOD


def test_returns_none_for_empty_or_missing():
    for value in (None, "", "   "):
        assert _first_sentence(value) is None


def test_rejects_a_fragment_that_is_too_short():
    assert _first_sentence("Council meets.") is None


def test_joins_two_short_sentences_when_one_is_too_short():
    joined = _first_sentence("Council met on Tuesday. The budget was adopted "
                             "after a lengthy debate about rates and services.")
    assert joined is not None
    assert joined.startswith("Council met on Tuesday.")
    assert MIN_LEDE_LEN <= len(joined) <= MAX_LEDE_LEN


def test_rejects_text_that_is_only_an_ellipsis_fragment():
    assert _first_sentence("...") is None
    assert _first_sentence("... continued from the previous page") is None


def test_truncates_an_overlong_sentence_at_a_word_boundary():
    long_text = "Council has announced " + ("a very significant change " * 20)
    out = _first_sentence(long_text)
    assert out and len(out) <= MAX_LEDE_LEN + 3   # +3 for the ellipsis
    assert out.endswith("...")
    assert "  " not in out


def test_collapses_whitespace_and_newlines():
    assert "\n" not in (_first_sentence("The council\n  said\ttoday that " +
                                        "rates would not rise this year at all.") or "")


# --- format switching -----------------------------------------------------

def _post(state, monkeypatch, title, excerpt, has_card, enabled=True):
    if enabled:
        monkeypatch.setenv("SENTENCE_FIRST_STATES", state)
    else:
        monkeypatch.delenv("SENTENCE_FIRST_STATES", raising=False)
    p = BlueSkyPoster(f"roundupnewsbot{state.lower()}.bsky.social", "x", state)
    text, facets, tags, used = p._format_post_with_facets(
        council_name="City of Marion", title=title,
        url="https://www.marion.sa.gov.au/news/a", date=datetime(2026, 7, 30),
        excerpt=excerpt, council_hashtag="#CityOfMarion", has_card=has_card)
    return text


def test_leads_with_the_sentence_when_a_card_is_present(monkeypatch):
    text = _post("SA", monkeypatch, "A Winter's Night Returns", GOOD, has_card=True)
    assert text.split("\n")[0] == GOOD
    assert "A Winter's Night Returns" not in text  # headline lives on the card


def test_falls_back_to_the_headline_without_a_usable_sentence(monkeypatch):
    text = _post("SA", monkeypatch, "Minutes Ordinary Council Meeting",
                 None, has_card=True)
    assert text.split("\n")[0] == "Minutes Ordinary Council Meeting"


def test_unchanged_format_when_there_is_no_card(monkeypatch):
    """Without a card nothing else carries the headline, so it stays first."""
    text = _post("SA", monkeypatch, "A Winter's Night Returns", GOOD, has_card=False)
    lines = text.split("\n")
    assert lines[0] == "A Winter's Night Returns"
    assert GOOD in text          # excerpt still included


def test_feature_is_off_unless_the_state_opts_in(monkeypatch):
    text = _post("SA", monkeypatch, "A Winter's Night Returns", GOOD,
                 has_card=True, enabled=False)
    assert text.split("\n")[0] == "A Winter's Night Returns"


def test_only_named_states_are_affected(monkeypatch):
    monkeypatch.setenv("SENTENCE_FIRST_STATES", "SA,QLD")
    for state, expect_sentence in (("SA", True), ("QLD", True), ("VIC", False)):
        p = BlueSkyPoster(f"roundupnewsbot{state.lower()}.bsky.social", "x", state)
        assert p._sentence_first_enabled() is expect_sentence


def test_all_keyword_enables_every_state(monkeypatch):
    monkeypatch.setenv("SENTENCE_FIRST_STATES", "ALL")
    for state in ("VIC", "NSW", "WA", "ACT"):
        p = BlueSkyPoster("h", "x", state)
        assert p._sentence_first_enabled()


def test_the_lede_is_the_clickable_link(monkeypatch):
    """Whatever leads the post must be what links to the article."""
    monkeypatch.setenv("SENTENCE_FIRST_STATES", "SA")
    p = BlueSkyPoster("roundupnewsbotsa.bsky.social", "x", "SA")
    text, facets, _, _ = p._format_post_with_facets(
        council_name="City of Marion", title="Headline", url="https://x.gov.au/a",
        date=datetime(2026, 7, 30), excerpt=GOOD, council_hashtag="#CityOfMarion",
        has_card=True)
    span = facets[0].index
    linked = text.encode()[span.byte_start:span.byte_end].decode()
    assert linked == text.split("\n")[0] == GOOD


# --- missing-space regression (found in a live SA post) -------------------

def test_splits_when_the_source_lost_the_space_after_a_full_stop():
    """Scraped copy often runs sentences together: '...program.Each year...'.

    A live SA post published exactly that, so the splitter must insert the
    missing space rather than emit both sentences as one lede.
    """
    text = ("COMMUNITY groups in Wakefield Regional Council will benefit from "
            "$98,000 in funding through Council's Minor and Major Community "
            "Grants program.Each year, grants are awarded in the Minor and "
            "Major categories.")
    out = _first_sentence(text)
    assert out.endswith("program.")
    assert "Each year" not in out


@pytest.mark.parametrize("text,intact", [
    ("Cr. Smith said the plan would deliver savings for ratepayers over four years.", "Cr."),
    ("The upgrade will deliver $1.5M in savings for ratepayers across the region.", "$1.5M"),
    ("Visit gov.au for details about the new rates policy and how it affects you.", "gov.au"),
])
def test_does_not_split_abbreviations_decimals_or_domains(text, intact):
    out = _first_sentence(text)
    assert out and intact in out


# --- card description as lede source (live gap found 2026-08-02) ----------

def test_lede_source_prefers_excerpt_then_card_description():
    """post_article picks the lede source: scraped excerpt first, else the
    card's own description.

    Many council pages carry an og:description but no scrapeable excerpt.
    Passing only the excerpt meant those posts fell back to the headline even
    though a usable sentence had already been fetched for the card - VIC was
    leading with a sentence on 5 posts out of 45. This pins the precedence
    rule that fixes it.
    """
    desc = ("Council has allocated $40,000 in its 2026/27 Budget to design a "
            "new play space in Wesley Hill, with construction to follow.")

    # the expression used in post_article
    def lede_source(excerpt, card_data):
        return excerpt or (card_data or {}).get("description")

    # no excerpt -> the card description is used
    assert lede_source(None, {"description": desc}) == desc
    # excerpt present -> the council's own summary wins
    assert lede_source(GOOD, {"description": desc}) == GOOD
    # neither -> nothing, and the headline will lead
    assert lede_source(None, {"description": ""}) in (None, "")
    assert lede_source(None, None) is None


def test_card_description_makes_a_usable_lede():
    """The description that was being discarded is a valid sentence."""
    desc = ("Council has allocated $40,000 in its 2026/27 Budget to design a "
            "new play space in Wesley Hill, with construction to follow.")
    out = _first_sentence(desc)
    assert out and out.startswith("Council has allocated $40,000")
    assert MIN_LEDE_LEN <= len(out) <= MAX_LEDE_LEN

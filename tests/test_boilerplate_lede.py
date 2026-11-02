"""Tests for keeping a site's tagline out of the post's first line.

The lede-from-description change (#36) takes og:description when the scraper
found no excerpt. On some platforms that field holds the website's own blurb
on every page, so the 2 Nov 2026 audit found three Moree stories in an hour
all opening "Moree Plains Shire Council, located in North West of New South
Wales, Australia." and five Augusta Margaret River ones opening "Latest Shire
news, public notices, opportunities to have your say". Production had 24
Stirling posts sharing one description.
"""
from datetime import datetime

import pytest

from core import link_card
from core.models import Article
from core.poster import BlueSkyPoster, _usable_description


WARREN = ("Welcome to Warren Shire. Information about the Council and the "
          "district, places of interest, events, library, address and contact numbers.")
MOREE = "Moree Plains Shire Council, located in North West of New South Wales, Australia."
STIRLING = "Keep up to date with the latest Council and Community News within the City of Stirling"
AMR = "Latest Shire news, public notices, opportunities to have your say"
REAL = ("Council will resurface twelve kilometres of highway shoulders between "
        "March and June, with night works on weekdays only.")


# ---- the pure decision ------------------------------------------------------

@pytest.mark.parametrize("tagline", [
    WARREN, STIRLING, AMR,
    "Click here for more information", "See here for more information.",
    "Find out more about the City of Mandurah, a place woven by waterways.",
])
def test_recognises_generic_taglines(tagline):
    assert _usable_description(tagline) is None


def test_rejects_the_councils_own_name():
    assert _usable_description("Penrith City Council", "Penrith City Council") is None
    assert _usable_description("Penrith City Council.", "Penrith City Council") is None


def test_keeps_a_real_summary():
    assert _usable_description(REAL, "Testville Shire Council") == REAL


def test_keeps_a_real_summary_that_merely_names_the_council():
    text = "Moree Plains Shire Council has adopted its 2026-27 budget with no rate rise."
    assert _usable_description(text, "Moree Plains Shire Council") == text


def test_rejects_when_the_lookup_says_it_recurs():
    assert _usable_description(MOREE, "Moree Plains Shire Council",
                               is_recurring=lambda d: True) is None


def test_keeps_when_the_lookup_says_it_is_new():
    assert _usable_description(REAL, "x", is_recurring=lambda d: False) == REAL


def test_a_failing_lookup_keeps_the_description():
    def boom(d):
        raise RuntimeError("db down")
    assert _usable_description(REAL, "x", is_recurring=boom) == REAL


def test_handles_empty():
    assert _usable_description(None) is None
    assert _usable_description("   ") is None


# ---- the database side ------------------------------------------------------

def _queue(db, url, council="amr"):
    db.add_articles_bulk([{
        "url": url, "council_id": council, "title": f"Story {url[-1]}",
        "date": datetime.now(), "excerpt": None,
    }], "WA")


def test_is_recurring_description_sees_an_earlier_post(db):
    _queue(db, "https://amr.wa.gov.au/news/1")
    db.mark_as_posted("https://amr.wa.gov.au/news/1", "h", {"og_description": AMR})
    assert db.is_recurring_description("amr", AMR) is True
    assert db.is_recurring_description("amr", REAL) is False
    # another council's tagline is not this council's
    assert db.is_recurring_description("mandurah", AMR) is False


def test_is_recurring_description_ignores_unposted_rows_and_empty(db):
    _queue(db, "https://amr.wa.gov.au/news/2")
    assert db.is_recurring_description("amr", AMR) is False
    assert db.is_recurring_description("amr", "") is False


# ---- through the poster -----------------------------------------------------

class CardClient:
    """Fake ATProto client that accepts an embed."""

    def __init__(self):
        self.posts = []

    def login(self, handle, password):
        return True

    def send_post(self, text, facets=None, embed=None):
        self.posts.append({"text": text, "embed": embed})
        return type("R", (), {"uri": "at://did:plc:x/app.bsky.feed.post/1", "cid": "c"})()


@pytest.fixture
def card_poster(monkeypatch):
    monkeypatch.setenv("LINK_CARDS_STATES", "VIC")
    monkeypatch.setenv("SENTENCE_FIRST_STATES", "VIC")
    monkeypatch.setattr(link_card, "build_external_embed", lambda *a, **k: object())

    def make(description):
        monkeypatch.setattr(link_card, "fetch_card_data", lambda url: {
            "uri": url, "title": "Highway shoulder works", "description": description, "image": None})
        p = BlueSkyPoster("roundupnewsbotvic.bsky.social", "pw", state_code="VIC")
        p.client = CardClient()
        p._authenticated = True
        return p

    return make


def _post(p, **kw):
    p.post_article("Testville Shire Council", "Highway shoulder works",
                   "https://testville.vic.gov.au/news/works", date=datetime(2026, 11, 2),
                   council_hashtag="#TestvilleShireCouncil", **kw)
    return p.client.posts[-1]["text"].split("\n")[0]


def test_a_real_description_leads_the_post(card_poster):
    assert _post(card_poster(REAL)) == REAL


def test_a_tagline_falls_back_to_the_headline(card_poster):
    assert _post(card_poster(WARREN)) == "Highway shoulder works"


def test_a_recurring_description_falls_back_to_the_headline(card_poster):
    first = _post(card_poster(REAL), description_is_recurring=lambda d: True)
    assert first == "Highway shoulder works"


def test_the_raw_description_is_still_recorded(card_poster):
    p = card_poster(WARREN)
    _post(p)
    assert p.last_post_meta["og_description"] == WARREN

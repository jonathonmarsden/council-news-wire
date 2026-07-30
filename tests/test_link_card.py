"""Tests for the rich link-card builder (core/link_card.py).

The central contract: link cards are additive and never destructive. Every
failure mode must return None so the caller falls back to the plain-text post.
All hermetic - no network.
"""
import sys
import types

import pytest

from core import link_card


# ---- title cleaning -------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Arbiter report tabled | City of Ballarat", "Arbiter report tabled"),
    ("News Story - DBCA to Manage Rabbits » Shire of Wongan-Ballidu",
     "DBCA to Manage Rabbits"),
    ("A Winter's Night Returns to Light Up Tonsley | News",
     "A Winter's Night Returns to Light Up Tonsley"),
    ("Plain headline with no cruft", "Plain headline with no cruft"),
    # leading generic labels (the real MacDonnell case + common variants)
    ("News Story - MRC Officially Opens New Change Rooms at Hermannsburg",
     "MRC Officially Opens New Change Rooms at Hermannsburg"),
    ("Media Release: Council adopts new budget", "Council adopts new budget"),
    ("Latest News | Pool reopens for summer", "Pool reopens for summer"),
    ("Announcement - Road closure this weekend", "Road closure this weekend"),
    # both ends at once
    ("News Story - Rabbits managed in park » Shire of Wongan-Ballidu",
     "Rabbits managed in park"),
])
def test_clean_title_strips_site_cruft(raw, expected):
    assert link_card.clean_title(raw) == expected


def test_clean_title_keeps_headline_that_merely_starts_with_news():
    # 'Newstead' / 'News for residents' must NOT be stripped as a label.
    assert link_card.clean_title("Newstead heritage listing approved") == \
        "Newstead heritage listing approved"


def test_clean_title_never_returns_empty():
    # If stripping would leave almost nothing, keep the original.
    raw = "News | City of X"
    assert link_card.clean_title(raw)  # non-empty


# ---- fetch_card_data fallbacks -------------------------------------------

class FakeResp:
    def __init__(self, status=200, text="", content=b"", ctype="text/html"):
        self.status_code = status
        self.text = text
        self.content = content
        self.headers = {"content-type": ctype}


def patch_get(monkeypatch, resp):
    monkeypatch.setattr(link_card._requests, "get", lambda *a, **k: resp)


PAGE = """<html><head>
<meta property="og:title" content="Real council story | City of Test">
<meta property="og:description" content="A useful summary of the story.">
<meta property="og:image" content="/files/pic.jpg">
</head></html>"""


def test_returns_none_on_http_error(monkeypatch):
    patch_get(monkeypatch, FakeResp(status=404, text="Not found"))
    assert link_card.fetch_card_data("https://x.gov.au/dead") is None


def test_returns_none_on_network_exception(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("reset")
    monkeypatch.setattr(link_card._requests, "get", boom)
    assert link_card.fetch_card_data("https://x.gov.au/a") is None


def test_returns_none_when_title_is_error_page(monkeypatch):
    patch_get(monkeypatch, FakeResp(text=
        '<html><head><meta property="og:title" content="Page not found"></head></html>'))
    assert link_card.fetch_card_data("https://x.gov.au/404") is None


def test_parses_and_cleans_good_page(monkeypatch):
    patch_get(monkeypatch, FakeResp(text=PAGE))
    d = link_card.fetch_card_data("https://x.gov.au/news/story")
    assert d["title"] == "Real council story"          # cruft stripped
    assert d["description"] == "A useful summary of the story."
    assert d["image"] == "https://x.gov.au/files/pic.jpg"  # resolved to absolute


def test_missing_image_still_returns_card(monkeypatch):
    patch_get(monkeypatch, FakeResp(text=
        '<html><head><meta property="og:title" content="Headline that is long enough">'
        '<meta property="og:description" content="desc"></head></html>'))
    d = link_card.fetch_card_data("https://x.gov.au/a")
    assert d is not None and d["image"] == ""


# ---- build_external_embed contract ---------------------------------------

class FakeBlobResp:
    def __init__(self): self.blob = {"$type": "blob", "ref": "fake"}


class FakeClient:
    def __init__(self, fail_upload=False):
        self.fail_upload = fail_upload
    def upload_blob(self, data):
        if self.fail_upload:
            raise RuntimeError("blob upload failed")
        return FakeBlobResp()


def fake_models():
    """Minimal stand-in for atproto.models with the two nested classes used."""
    m = types.SimpleNamespace()
    ext = types.SimpleNamespace(
        External=lambda **kw: ("External", kw),
        Main=lambda external: ("Main", external),
    )
    m.AppBskyEmbedExternal = ext
    return m


def test_embed_none_when_page_unusable(monkeypatch):
    patch_get(monkeypatch, FakeResp(status=404))
    assert link_card.build_external_embed(FakeClient(), fake_models(), "https://x/dead") is None


def test_no_image_falls_back_to_text_by_default(monkeypatch):
    # Default require_image=True: a page with no og:image -> None (post plain text)
    patch_get(monkeypatch, FakeResp(text=
        '<html><head><meta property="og:title" content="Headline long enough here">'
        '<meta property="og:description" content="d"></head></html>'))
    assert link_card.build_external_embed(FakeClient(), fake_models(), "https://x/a") is None


def test_no_image_allowed_when_require_image_false(monkeypatch):
    patch_get(monkeypatch, FakeResp(text=
        '<html><head><meta property="og:title" content="Headline long enough here">'
        '<meta property="og:description" content="d"></head></html>'))
    embed = link_card.build_external_embed(
        FakeClient(), fake_models(), "https://x/a", require_image=False)
    assert embed is not None
    assert embed[1][1]["thumb"] is None  # text-card, no thumb


def test_embed_with_image_is_built(monkeypatch):
    # og:image present and blob upload succeeds -> full card with thumb
    monkeypatch.setattr(link_card._requests, "get",
                        lambda *a, **k: FakeResp(text=PAGE, content=b"imgbytes", ctype="image/jpeg"))
    embed = link_card.build_external_embed(FakeClient(), fake_models(), "https://x/a")
    assert embed is not None
    assert embed[1][1]["thumb"] is not None


def test_blob_upload_failure_falls_back_to_text_by_default(monkeypatch):
    # og:image present but blob upload throws -> no thumb -> None under default
    monkeypatch.setattr(link_card._requests, "get",
                        lambda *a, **k: FakeResp(text=PAGE, content=b"imgbytes", ctype="image/jpeg"))
    assert link_card.build_external_embed(
        FakeClient(fail_upload=True), fake_models(), "https://x/a") is None


def test_embed_never_raises(monkeypatch):
    def boom(*a, **k):
        raise ValueError("anything")
    monkeypatch.setattr(link_card, "fetch_card_data", boom)
    # must swallow and return None, never propagate into the posting path
    assert link_card.build_external_embed(FakeClient(), fake_models(), "https://x/a") is None

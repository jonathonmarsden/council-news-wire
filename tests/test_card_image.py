"""Tests for the branded fallback card renderer (core/card_image.py).

Council headlines are not tidy - some run past 100 characters, some are a
single unbroken word - and a card that overflows or crashes is worse than the
plain text post it replaces. These tests pin the size/format contract and the
awkward-input behaviour.
"""
import pytest

from core import card_image

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _open(data):
    from PIL import Image
    import io
    return Image.open(io.BytesIO(data))


def test_renders_png_at_card_dimensions():
    data = card_image.render_card("Pool opening hours change",
                                  "Moyne Shire Council", "VIC", "28 July 2026")
    assert data and data.startswith(PNG_MAGIC)
    img = _open(data)
    assert img.size == (card_image.CARD_W, card_image.CARD_H) == (1200, 630)


@pytest.mark.parametrize("title", [
    "Notice of intended pesticide application along the Macintyre River pursuant to section 51 of the Act",
    "Supercalifragilisticexpialidociousantidisestablishmentarianism",  # one long word
    "Minutes Ordinary Council Meeting - Tuesday 28 July 2026",
    "$15,000 set to flow into East Freo organisations",
    "Council adopts Budget with focus on the fundamentals",
])
def test_awkward_titles_still_render(title):
    data = card_image.render_card(title, "Some Shire Council", "WA", "1 Aug 2026")
    assert data and data.startswith(PNG_MAGIC)
    assert _open(data).size == (1200, 630)


def test_empty_title_does_not_crash():
    data = card_image.render_card("", "Some Council", "NSW", "")
    assert data and data.startswith(PNG_MAGIC)


def test_state_accent_differs_between_states():
    """The spine colour identifies the state; VIC and NSW must not match."""
    vic = _open(card_image.render_card("T", "C", "VIC")).getpixel((5, 300))
    nsw = _open(card_image.render_card("T", "C", "NSW")).getpixel((5, 300))
    assert vic != nsw
    assert vic == card_image.STATE_COLOURS["VIC"]


def test_unknown_state_uses_default_accent():
    px = _open(card_image.render_card("T", "C", "ZZZ")).getpixel((5, 300))
    assert px == card_image.DEFAULT_ACCENT


def test_background_is_brand_navy():
    # sample a point clear of the spine and any text
    px = _open(card_image.render_card("T", "C", "VIC")).getpixel((1100, 60))
    assert px == card_image.NAVY


def test_excerpt_is_optional():
    without = card_image.render_card("Council backs local events", "C", "VIC", "1 Aug 2026")
    with_sub = card_image.render_card("Council backs local events", "C", "VIC", "1 Aug 2026",
                                      "Twelve events share $45,000 this round.")
    assert without and with_sub
    assert without != with_sub  # the excerpt actually changes the render


def test_returns_none_without_pillow(monkeypatch):
    """No Pillow -> None, so the caller posts plain text instead of failing."""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("no PIL")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert card_image.render_card("T", "C", "VIC") is None

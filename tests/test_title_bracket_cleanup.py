"""Vue hydration markers must not survive into titles.

Vue and similar frameworks mark fragment boundaries with comment nodes
(<!--[--> ... <!--]-->). Stripping HTML leaves the bare brackets behind, so a
Sunshine Coast headline was stored as "[ [ Sport, food and fun ] ]" - 146
titles in the archive look like that.

The rule has to be narrow: stripping any leading bracket would turn a real
title like "[2026] Annual Report released" into "2026] Annual Report released",
which is worse than leaving the markup in place.
"""
import pytest

from core.scrapers.base import BaseScraper


class _Scraper(BaseScraper):
    def scrape(self):  # pragma: no cover
        return []


@pytest.fixture
def scraper():
    return _Scraper("x", "X", "https://example.gov.au/news")


@pytest.mark.parametrize("raw,expected", [
    ("[ [ Sport, food and fun: your guide to August events ] ]",
     "Sport, food and fun: your guide to August events"),
    ("[ [ Nature's smallest engineers found in Bli Bli ] ]",
     "Nature's smallest engineers found in Bli Bli"),
    ("[ Single wrapper ]", "Single wrapper"),
])
def test_hydration_brackets_are_stripped(scraper, raw, expected):
    assert scraper.clean_text(raw) == expected


@pytest.mark.parametrize("raw", [
    "[2026] Annual Report released",
    "Council adopts [Draft] Budget 2026",
    "Notice [amended] for the Wednesday meeting",
])
def test_meaningful_brackets_are_preserved(scraper, raw):
    """An unbalanced or content-bearing bracket is part of the headline."""
    assert scraper.clean_text(raw) == raw


def test_a_plain_title_is_untouched(scraper):
    assert scraper.clean_text("Normal headline with no brackets") == \
        "Normal headline with no brackets"

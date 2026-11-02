"""Tests for decoding HTML entities that have lost their semicolon.

Found in the 2 Nov 2026 feed audit: SA posts reading "Council&rsquo s current
suite of By-laws" and "NOTICE &ndash PLANNED CONTROLLED BURN-OFF". The LGA SA
platform double-encodes its teasers and drops the semicolon on the way
("&amp;rsquo s" in the source), so one html.unescape leaves "&rsquo s" behind.
The same audit found Bayside's titles full of Drupal "THEME DEBUG" comments.
"""
import pytest

from core.utils import repair_entities
from core.scrapers.card import CardScraper


@pytest.mark.parametrize("raw,expected", [
    # the real Streaky Bay teaser, as served
    ("The State Government&amp;rsquo s 12-month free boat ramp access initiative",
     "The State Government’s 12-month free boat ramp access initiative"),
    # already single-decoded (what the queue held)
    ("Council&rsquo s current suite of By-laws", "Council’s current suite of By-laws"),
    # a dash keeps its spacing
    ("NOTICE &ndash PLANNED CONTROLLED BURN-OFF", "NOTICE – PLANNED CONTROLLED BURN-OFF"),
    # the footer of the same CMS
    ("Clare &amp Gilbert Valleys Council", "Clare & Gilbert Valleys Council"),
    # ordinary, well-formed entities still decode
    ("Council&rsquo;s plan &amp; budget", "Council’s plan & budget"),
    # numeric form
    ("Council&#8217 s plan", "Council’s plan"),
])
def test_repairs_entities_missing_their_semicolon(raw, expected):
    assert repair_entities(raw) == expected


def test_rejoins_a_contraction_split_by_the_lost_semicolon():
    assert repair_entities("We&rsquo re open, don&rsquo t miss it") == "We’re open, don’t miss it"


@pytest.mark.parametrize("text", [
    "AT&T and R&D", "M&Ms for the kids", "Fish & chips", "Q&A session",
    "the ‘best’ s-bend in town",
])
def test_leaves_ampersands_that_are_not_entities_alone(text):
    assert repair_entities(text) == text


def test_handles_empty_and_none():
    assert repair_entities(None) is None
    assert repair_entities("") == ""


def test_clean_text_uses_the_repair():
    s = CardScraper("t", "Testville", "https://t.gov.au/news")
    assert s.clean_text("<p>Council&amp;rsquo s plan</p>") == "Council’s plan"


# ---- HTML comments are not content ----------------------------------------

BAYSIDE_ITEM = """
<article class="event-teaser">
  <h3 class="event-teaser__title">
    <!-- THEME DEBUG -->
    <!-- THEME HOOK: 'field' -->
    <!-- FILE NAME SUGGESTIONS: ▪️ field--node--title.html.twig -->
    <a class="event-teaser__link" href="/your-council/latest-news/council-adopts-plan">
      Council Adopts Rockdale Centre Masterplan</a>
    <!-- END OUTPUT from 'themes/custom/bayside/templates/field.html.twig' -->
  </h3>
</article>
"""


def test_parse_html_drops_comments_so_titles_stay_clean():
    s = CardScraper("bayside", "Bayside Council", "https://www.bayside.nsw.gov.au/news")
    soup = s.parse_html(BAYSIDE_ITEM)
    # Bayside's config reads the anchor itself: its class contains "teaser",
    # which the metadata filter in _get_clean_title would otherwise skip.
    title = s._get_clean_title(soup.select_one(".event-teaser__title a"))
    assert title == "Council Adopts Rockdale Centre Masterplan"
    assert "THEME" not in title


def test_title_walk_ignores_comments_even_without_parse_html():
    from bs4 import BeautifulSoup
    s = CardScraper("t", "Testville", "https://t.gov.au/news")
    el = BeautifulSoup("<h2><!-- THEME DEBUG -->Pool reopens<span class='date'>1 Nov</span></h2>",
                       "html.parser").h2
    assert s._get_clean_title(el) == "Pool reopens"

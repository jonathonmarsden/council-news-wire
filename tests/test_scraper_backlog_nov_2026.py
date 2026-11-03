"""Tests for the two parser changes made while repairing the November 2026
scraper backlog (17 councils tripped by the circuit breaker).

Central Highlands TAS writes its listing date as "Oct 29 | 2026"; the pipe
reached dateutil and the date was lost. Northampton prefixes every title
with "MEDIA RELEASE – " using an en-dash, which the prefix strip did not
eat, leaving "– SHIRE OF NORTHAMPTON ...".
"""
from datetime import datetime

import pytest
from bs4 import BeautifulSoup

from core.scrapers.card import CardScraper


@pytest.fixture
def scraper():
    return CardScraper("t", "Testville", "https://t.gov.au/news")


@pytest.mark.parametrize("raw,expected", [
    ("Oct 29 | 2026", datetime(2026, 10, 29)),
    ("Oct 29 |2026", datetime(2026, 10, 29)),
    ("Posted 12 October 2026", datetime(2026, 10, 12)),
    ("Published | 3 November 2026", datetime(2026, 11, 3)),
    ("28 Nov 2025", datetime(2025, 11, 28)),
])
def test_parse_date_ignores_decorative_pipes(scraper, raw, expected):
    assert scraper.parse_date(raw) == expected


@pytest.mark.parametrize("html,expected", [
    ("<h2>MEDIA RELEASE – SHIRE OF NORTHAMPTON APPOINTS NEW CEO</h2>", "SHIRE OF NORTHAMPTON APPOINTS NEW CEO"),
    ("<h2>Media Release — Pool reopens</h2>", "Pool reopens"),
    ("<h2>Media Release - Pool reopens</h2>", "Pool reopens"),
    ("<h2>Media Release: Pool reopens</h2>", "Pool reopens"),
    ("<h2>Pool reopens – stage two</h2>", "Pool reopens – stage two"),
])
def test_title_prefix_strip_eats_en_and_em_dashes(scraper, html, expected):
    el = BeautifulSoup(html, "html.parser").h2
    assert scraper._get_clean_title(el) == expected

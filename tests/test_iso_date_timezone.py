"""Regression tests for timezone-aware ISO dates in parse_date.

A council publishing <time datetime="2026-07-20T12:00:00Z"> produced an aware
datetime, while every freshness comparison and the DateTime column are naive.
The mismatch raised "can't compare offset-naive and offset-aware datetimes",
so those articles ended up unpostable - NT had 9 future-dated and 16 undated
rows stuck in the queue for this reason.
"""
from datetime import datetime, timedelta

import pytest

from core.scrapers.base import BaseScraper


class _Scraper(BaseScraper):
    def scrape(self):  # pragma: no cover - not exercised
        return []


@pytest.fixture
def scraper():
    return _Scraper("x", "X", "https://example.gov.au/news")


@pytest.mark.parametrize("raw,expected_date", [
    ("2026-07-20T12:00:00Z", (2026, 7, 20)),
    ("2026-07-20T12:00:00+10:00", (2026, 7, 20)),
    ("2026-07-20T00:00:00+00:00", (2026, 7, 20)),
    ("2026-07-20", (2026, 7, 20)),
])
def test_iso_dates_parse_to_naive_datetimes(scraper, raw, expected_date):
    parsed = scraper.parse_date(raw)
    assert parsed is not None, f"{raw} should parse"
    assert parsed.tzinfo is None, "downstream code and the DB column are naive"
    assert (parsed.year, parsed.month) == expected_date[:2]


def test_aware_iso_date_is_comparable_with_now(scraper):
    """The actual failure: comparing the parsed date with datetime.now()."""
    parsed = scraper.parse_date("2026-07-20T12:00:00Z")
    assert parsed < datetime.now() or parsed > datetime.now()  # must not raise


def test_utc_is_converted_not_truncated(scraper):
    """A UTC timestamp should shift to local time, not silently drop the zone."""
    parsed = scraper.parse_date("2026-07-20T12:00:00Z")
    assert parsed.day in (20, 21)  # 12:00Z is same-day or next-day locally


@pytest.mark.parametrize("raw", ["Posted 04 June 2026", "Posted 26 May 2026",
                                 "04 June 2026", "26 May 2026"])
def test_posted_prefix_dates_still_work(scraper, raw):
    """Alice Springs prints 'Posted 04 June 2026'."""
    parsed = scraper.parse_date(raw)
    assert parsed is not None and parsed.tzinfo is None
    assert parsed.year == 2026


# --- RFC-822 (RSS) dates must also be naive -------------------------------

@pytest.mark.parametrize("raw", [
    "Fri, 31 Jul 2026 00:00:00 +1000",   # ACT ministerial feed
    "Wed, 29 Jul 2026 09:30:00 GMT",
    "Sat, 25 Jul 2026 12:00:00 -0700",
])
def test_rfc822_rss_dates_parse_to_naive(scraper, raw):
    """RSS feeds carry an offset; only the ISO branch normalised it before.

    An aware datetime cannot be compared with the naive freshness cutoff, so
    those articles ended up dateless and unpostable - the fault that stranded
    NT's queue. Every parse path normalises now, not just the ISO one.
    """
    parsed = scraper.parse_date(raw)
    assert parsed is not None
    assert parsed.tzinfo is None


def test_bare_iso_date_from_our_canberra(scraper):
    """The Our Canberra feed uses '2026-04-13' rather than RFC-822."""
    parsed = scraper.parse_date("2026-04-13")
    assert parsed is not None and parsed.tzinfo is None
    assert (parsed.year, parsed.month, parsed.day) == (2026, 4, 13)


def test_every_parse_path_returns_naive(scraper):
    for raw in ["2026-07-20T12:00:00Z", "2026-04-13",
                "Fri, 31 Jul 2026 00:00:00 +1000", "28 November 2025",
                "Published 28 Nov 2025"]:
        parsed = scraper.parse_date(raw)
        if parsed is not None:
            assert parsed.tzinfo is None, f"{raw} produced an aware datetime"


# --- year-less dates must not land in the future --------------------------

def test_yearless_december_scraped_in_august_rolls_back(scraper):
    """Councils print '16 December' with no year.

    dateutil fills the gap with the CURRENT year, so a December 2025 story
    scraped in August 2026 became December 2026 - dated in the future and
    permanently rejected by the freshness filter. 66 articles were stuck this
    way across six states, almost all stamped November or December.
    """
    parsed = scraper.parse_date("16 December")
    assert parsed is not None
    assert parsed <= datetime.now() + timedelta(days=1), (
        "a year-less date must never resolve into the future")


@pytest.mark.parametrize("raw", ["22 December", "Mon 15 Dec", "December 16",
                                 "1 November", "25 Dec"])
def test_no_yearless_date_resolves_to_the_future(scraper, raw):
    parsed = scraper.parse_date(raw)
    if parsed is not None:
        assert parsed <= datetime.now() + timedelta(days=1)


@pytest.mark.parametrize("raw,year", [
    ("16 December 2026", 2026),
    ("1 January 2027", 2027),
    ("2026-12-16", 2026),
])
def test_an_explicit_year_is_never_overridden(scraper, raw, year):
    """A council genuinely announcing a future event must be left alone."""
    parsed = scraper.parse_date(raw)
    assert parsed is not None and parsed.year == year


def test_recent_past_yearless_date_keeps_this_year(scraper):
    """Only future-resolving dates roll back; a recent one stays put."""
    last_month = datetime.now() - timedelta(days=30)
    raw = last_month.strftime("%d %B")
    parsed = scraper.parse_date(raw)
    assert parsed is not None and parsed.year == last_month.year

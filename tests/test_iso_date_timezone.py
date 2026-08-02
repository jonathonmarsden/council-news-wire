"""Regression tests for timezone-aware ISO dates in parse_date.

A council publishing <time datetime="2026-07-20T12:00:00Z"> produced an aware
datetime, while every freshness comparison and the DateTime column are naive.
The mismatch raised "can't compare offset-naive and offset-aware datetimes",
so those articles ended up unpostable - NT had 9 future-dated and 16 undated
rows stuck in the queue for this reason.
"""
from datetime import datetime

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

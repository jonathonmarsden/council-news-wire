"""The scrapers only fetch public web addresses.

Links are taken from council pages. A compromised page must not be able to
make the bot read local files or call addresses inside its own network.
"""
from unittest.mock import MagicMock, patch

import pytest

from core.scrapers.card import CardScraper


@pytest.fixture
def scraper():
    return CardScraper("example", "Example Council", "https://example.test/news/")


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "gopher://db:5432/_x",
    "ftp://example.test/a",
    "http://127.0.0.1/admin",
    "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/",
    "-o/tmp/x",
    "",
])
def test_refused_addresses_are_never_requested(scraper, url):
    scraper.session.get = MagicMock(side_effect=AssertionError("must not be requested"))
    scraper.session.head = MagicMock(side_effect=AssertionError("must not be requested"))
    with patch("subprocess.run", side_effect=AssertionError("must not run curl")):
        assert scraper.fetch_page(url) is None
        assert scraper.file_modified_date(url) is None


def test_public_address_is_allowed(scraper):
    with patch("core.link_card.socket.getaddrinfo",
               return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        assert scraper.is_fetchable("https://www.example.gov.au/news/story")


def test_name_that_resolves_to_a_private_address_is_refused(scraper):
    with patch("core.link_card.socket.getaddrinfo",
               return_value=[(2, 1, 6, "", ("10.0.0.5", 0))]):
        assert not scraper.is_fetchable("https://intranet.example.gov.au/")

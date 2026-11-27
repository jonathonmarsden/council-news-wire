"""Newsletter archives: dates from the file's server header, and the
WordPress media library as a source."""
from datetime import datetime
from unittest.mock import MagicMock

from core.scrapers.card import CardScraper
from core.scrapers.custom import WordPressScraper

PAGE = """
<html><body>
  <a href="https://example.test/files/statement.pdf">Public statement on dogs</a>
  <a href="https://example.test/files/oct-nov.pdf">Oct / Nov 2026</a>
  <a href="https://example.test/files/undated.pdf">September /October 2026</a>
  <a href="/about">About</a>
</body></html>
"""

HEADERS = {
    "https://example.test/files/statement.pdf": "Fri, 07 Aug 2026 02:54:24 GMT",
    "https://example.test/files/oct-nov.pdf": "Wed, 11 Nov 2026 00:05:58 GMT",
}


def make_scraper(**kwargs):
    scraper = CardScraper(
        "example", "Example Council", "https://example.test/news/",
        selectors={"item_selector": 'a[href$=".pdf"]', "link_selector": "self",
                   "title_selector": "self"},
        **kwargs)
    scraper.fetch_page_or_raise = lambda url: PAGE

    def head(url, **_):
        response = MagicMock()
        response.status_code = 200
        response.headers = {"Last-Modified": HEADERS[url]} if url in HEADERS else {}
        return response
    scraper.session.head = head
    return scraper


def test_date_comes_from_the_file_and_undated_items_are_dropped():
    articles = make_scraper(date_from_file_header=True).scrape()
    assert [a.url for a in articles] == list(HEADERS)
    assert all(isinstance(a.date, datetime) for a in articles)
    assert (articles[0].date.year, articles[0].date.month) == (2026, 8)


def test_prefix_goes_only_on_titles_that_are_just_a_period():
    articles = make_scraper(date_from_file_header=True,
                            bare_title_prefix="Council newsletter: ").scrape()
    assert [a.title for a in articles] == [
        "Public statement on dogs", "Council newsletter: Oct / Nov 2026"]


def test_without_the_option_nothing_changes():
    scraper = make_scraper()
    scraper.session.head = MagicMock(side_effect=AssertionError("no HEAD expected"))
    articles = scraper.scrape()
    assert len(articles) == 3
    assert articles[1].title == "Oct / Nov 2026"


def test_bare_period_titles():
    scraper = make_scraper()
    assert scraper.is_bare_period_title("March-April 2026")
    assert scraper.is_bare_period_title("May/ June 2026")
    assert not scraper.is_bare_period_title("March 2026 Newsletter")
    assert not scraper.is_bare_period_title("2026")


def test_wordpress_reads_an_api_address_and_links_to_the_file():
    url = "https://example.test/wp-json/wp/v2/media?search=Council-Corner"
    scraper = WordPressScraper("example", "Example Council", url)
    assert scraper.api_url == url
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = [{
        "title": {"rendered": "Council Corner Oct 2026"},
        "link": "https://example.test/council-corner-oct-2026/",
        "source_url": "https://example.test/uploads/Council-Corner-Oct-2026.pdf",
        "date": "2026-10-26T12:27:53",
    }]
    scraper.session.get = MagicMock(return_value=response)
    articles = scraper.scrape()
    assert articles[0].url == "https://example.test/uploads/Council-Corner-Oct-2026.pdf"
    assert articles[0].date == datetime(2026, 10, 26, 12, 27, 53)
    assert scraper.session.get.call_args[0][0].endswith("search=Council-Corner&per_page=20")


def test_wordpress_posts_address_is_still_derived():
    scraper = WordPressScraper("example", "Example Council", "https://example.test/news/")
    assert scraper.api_url == "https://example.test/wp-json/wp/v2/posts"

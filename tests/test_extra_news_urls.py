"""A council can be read from more than one page (`extra_news_urls`)."""
import pytest

from core.scrapers.base import NewsArticle
from core.scrapers.factory import MultiSourceScraper, ScraperFactory

COUNCIL = {
    "id": "example",
    "name": "Shire of Example",
    "news_url": "https://example.test/news/",
    "scraper": "catalyst_scraper",
}


class Stub:
    council_id = "example"

    def __init__(self, url, result):
        self.news_url = url
        self.result = result

    def scrape(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def article(url):
    return NewsArticle(title="A notice", url=url, council_id="example",
                       council_name="Shire of Example")


def test_single_page_council_is_unchanged():
    scraper = ScraperFactory.create_scraper(dict(COUNCIL))
    assert not isinstance(scraper, MultiSourceScraper)


def test_extra_pages_use_the_same_scraper_type():
    council = dict(COUNCIL, extra_news_urls=["https://example.test/publicnotices/"])
    scraper = ScraperFactory.create_scraper(council)
    assert isinstance(scraper, MultiSourceScraper)
    assert [s.news_url for s in scraper.scrapers] == [
        "https://example.test/news/", "https://example.test/publicnotices/"]
    assert len({type(s) for s in scraper.scrapers}) == 1
    assert scraper.news_url == "https://example.test/news/"


def test_results_are_merged_and_a_repeated_story_kept_once():
    a, b = article("https://example.test/a"), article("https://example.test/b")
    merged = MultiSourceScraper(Stub("one", [a]), [Stub("two", [a, b])]).scrape()
    assert [x.url for x in merged] == ["https://example.test/a", "https://example.test/b"]


def test_a_failing_extra_page_does_not_lose_the_news():
    a = article("https://example.test/a")
    merged = MultiSourceScraper(Stub("one", [a]), [Stub("two", RuntimeError("down"))]).scrape()
    assert [x.url for x in merged] == ["https://example.test/a"]


def test_a_failing_news_page_is_raised_even_if_an_extra_page_works():
    b = article("https://example.test/b")
    with pytest.raises(RuntimeError):
        MultiSourceScraper(Stub("one", RuntimeError("down")), [Stub("two", [b])]).scrape()


def test_failure_is_raised_when_only_extras_fail_and_nothing_is_returned():
    with pytest.raises(RuntimeError):
        MultiSourceScraper(Stub("one", []), [Stub("two", RuntimeError("down"))]).scrape()

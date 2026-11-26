"""Bunbury's API returns links on its API host; readers need the public URL."""
from core.scrapers.custom import BunburyScraper


def test_api_link_becomes_public_story_url():
    link = "https://cdnng.bunbury.wa.gov.au/have-your-say-on-the-future-of-back-beach/"
    assert BunburyScraper.public_url(link) == (
        "https://www.bunbury.wa.gov.au/news/have-your-say-on-the-future-of-back-beach"
    )


def test_link_without_a_slug_is_left_alone():
    link = "https://cdnng.bunbury.wa.gov.au/"
    assert BunburyScraper.public_url(link) == link


def test_scraper_reads_the_current_api_host():
    scraper = BunburyScraper("bunbury", "City of Bunbury", "https://www.bunbury.wa.gov.au/news")
    assert scraper.api_url == "https://cdnng.bunbury.wa.gov.au/wp-json/wp/v2/posts"

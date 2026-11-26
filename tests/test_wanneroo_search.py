"""WannerooScraper reads the JSON the council's news page loads its list from."""
from core.scrapers.wa_custom import WannerooScraper

PAYLOAD = {
    "Total": 2,
    "Data": [
        {
            "ArticleTitle": "New era for Wanneroo Recreation Centre",
            "PageUrl": "/city-and-council/latest-news/new-era-for-wanneroo-recreation-centre",
            "ArticleReleaseDate": "2026-11-25T00:00:00",
            "ArticleSummary": "The centre reopens after a major upgrade.",
        },
        {"ArticleTitle": "", "PageUrl": "/city-and-council/latest-news/untitled"},
        {"ArticleTitle": "No link"},
    ],
}


def _scraper():
    return WannerooScraper("wanneroo", "City of Wanneroo",
                           "https://www.wanneroo.wa.gov.au/city-and-council/latest-news")


def test_results_become_articles():
    articles = _scraper().parse_results(PAYLOAD)
    assert len(articles) == 1
    article = articles[0]
    assert article.title == "New era for Wanneroo Recreation Centre"
    assert article.url == ("https://www.wanneroo.wa.gov.au/city-and-council/latest-news/"
                           "new-era-for-wanneroo-recreation-centre")
    assert (article.date.year, article.date.month, article.date.day) == (2026, 11, 25)
    assert article.excerpt == "The centre reopens after a major upgrade."


def test_empty_payload_gives_no_articles():
    assert _scraper().parse_results({}) == []
    assert _scraper().parse_results({"Data": None}) == []

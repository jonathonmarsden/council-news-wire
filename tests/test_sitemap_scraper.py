"""Sitemap scraper: parsing, ordering, and title tidying (no network)."""
from core.scrapers.sitemap import parse_sitemap, tidy_title, title_from_slug

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://x.example/public-notices-1/older</loc><lastmod>2026-08-05</lastmod></url>
  <url><loc>https://x.example/council-meetings/agenda</loc><lastmod>2026-11-09</lastmod></url>
  <url><loc>https://x.example/public-notices-1/newer</loc><lastmod>2026-10-30</lastmod></url>
  <url><loc>https://x.example/public-notices-1/undated</loc></url>
</urlset>"""


def test_sitemap_filters_and_sorts_newest_first():
    pages = parse_sitemap(SITEMAP, "/public-notices-1/")
    assert [u.rsplit("/", 1)[1] for u, _ in pages] == ["newer", "older", "undated"]
    assert pages[0][1].date().isoformat() == "2026-10-30"
    assert pages[-1][1] is None


def test_all_caps_title_is_title_cased():
    assert tidy_title("NOTICE OF INTENTION TO IMPOSE DIFFERENTIAL RATES") == \
        "Notice of Intention to Impose Differential Rates"
    assert tidy_title("PRE-CYCLONE SEASON CLEAN UP") == "Pre-Cyclone Season Clean Up"


def test_mixed_case_title_untouched():
    assert tidy_title("Council meets on Tuesday") == "Council meets on Tuesday"


def test_multiline_title_drops_council_name_and_acts():
    raw = ("SHIRE OF CHRISTMAS ISLAND\nPLANNING AND DEVELOPMENT ACT 2005\n"
           "PLANNING AND DEVELOPMENT (LOCAL PLANNING SCHEMES) REGULATIONS 2015\n\n"
           "NOTICE OF PUBLIC ADVERTISEMENT OF DRAFT LOCAL PLANNING STRATEGY")
    assert tidy_title(raw, "Shire of Christmas Island") == \
        "Notice of Public Advertisement of Draft Local Planning Strategy"


def test_multiline_title_lines_are_joined():
    assert tidy_title("ROAD SAFETY NOTICE\nCHRISTMAS ISLAND MARATHON") == \
        "Road Safety Notice - Christmas Island Marathon"


def test_slug_fallback():
    assert title_from_slug("https://x.example/public-notices-1/pre-cyclone-season-clean-up") == \
        "Pre Cyclone Season Clean Up"

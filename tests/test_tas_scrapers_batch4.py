import pytest
from core.scrapers import CardScraper, RSSScraper
from main import load_state_config, get_scraper

@pytest.fixture
def tas_config():
    return load_state_config('tas')

def get_council_config(tas_config, council_id):
    for council in tas_config['councils']:
        if council['id'] == council_id:
            return council
    return None

def test_break_o_day_scraper(tas_config):
    config = get_council_config(tas_config, 'break-o-day')
    assert config is not None
    scraper = get_scraper(config)
    articles = scraper.scrape()
    assert len(articles) > 0
    # Check for a known recent article or just structure
    # "What's Happening?" or "NOTICE OF INTENTION"
    assert any(len(a.title) > 5 for a in articles)

def test_brighton_scraper(tas_config):
    config = get_council_config(tas_config, 'brighton')
    assert config is not None
    scraper = get_scraper(config)
    articles = scraper.scrape()
    assert len(articles) > 0
    # Check for "Media Release" or similar
    assert any(len(a.title) > 5 for a in articles)

def test_central_highlands_scraper(tas_config):
    config = get_council_config(tas_config, 'central-highlands')
    assert config is not None
    scraper = get_scraper(config)
    assert isinstance(scraper, RSSScraper)
    articles = scraper.scrape()
    assert len(articles) > 0
    # Check for "Notice of Annual General Meeting" which we saw in the feed
    assert any("Annual General Meeting" in a.title for a in articles)

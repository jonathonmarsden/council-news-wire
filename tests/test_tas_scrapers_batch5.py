import pytest
from core.scraper import ScraperFactory
from core.database import Database
import json
import os

# Batch 5: Circular Head, Derwent Valley, Kentish
# These councils use Squiz Matrix and require mobile_mode to bypass Cloudflare WAF.

@pytest.fixture
def councils():
    with open('states/tas/councils.json', 'r') as f:
        return json.load(f)['councils']

def get_council_config(councils, council_id):
    for council in councils:
        if council['id'] == council_id:
            return council
    return None

@pytest.mark.parametrize("council_id", [
    "circular-head",
    "derwent-valley",
    "kentish"
])
def test_batch5_scrapers(councils, council_id):
    config = get_council_config(councils, council_id)
    assert config is not None, f"Council {council_id} not found in config"
    
    # Ensure mobile_mode is enabled
    assert config.get('mobile_mode') is True, f"{council_id} should have mobile_mode=True"
    assert config.get('scraper') == 'curl_scraper', f"{council_id} should use curl_scraper"
    
    scraper = ScraperFactory.create_scraper(config)
    articles = scraper.scrape()
    
    print(f"\nScraped {len(articles)} articles for {council_id}")
    for article in articles[:3]:
        print(f"- {article.title} ({article.date})")
        print(f"  URL: {article.url}")
    
    assert len(articles) > 0, f"No articles found for {council_id}"
    
    # Check for valid data
    for article in articles:
        assert article.title, "Article must have a title"
        assert article.url, "Article must have a URL"
        # Date might be missing if parsing fails, but we should try to get it
        if not article.date:
            print(f"Warning: No date for article: {article.title}")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

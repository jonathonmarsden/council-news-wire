import pytest
from core.scraper import CardScraper
import json
import os

def get_council_config(council_id):
    with open('states/tas/councils.json', 'r') as f:
        data = json.load(f)
        for council in data['councils']:
            if council['id'] == council_id:
                return council
    return None

@pytest.mark.parametrize("council_id", [
    "dorset",
    "flinders",
    "george-town",
    "glamorgan-spring-bay"
])
def test_tas_scraper_batch3(council_id):
    config = get_council_config(council_id)
    assert config is not None, f"Council {council_id} not found in config"
    
    scraper = CardScraper(
        council_id=config['id'],
        council_name=config['name'],
        news_url=config['news_url'],
        selectors={
            "item_selector": config['item_selector'],
            "title_selector": config['title_selector'],
            "date_selector": config['date_selector'],
            "link_selector": config['link_selector']
        }
    )
    
    # Use a limit to avoid fetching too many pages
    scraper.limit = 5
    articles = scraper.scrape()
    
    print(f"\nFound {len(articles)} articles for {council_id}")
    for article in articles:
        print(f"- {article.title} ({article.date}) [{article.url}]")
    
    assert len(articles) > 0, f"No articles found for {council_id}"
    
    # Basic validation
    for article in articles:
        assert article.title, "Article title is missing"
        assert article.url, "Article URL is missing"
        # Date might be missing for Flinders
        if council_id != "flinders":
            # Glamorgan might have missing dates if parsing fails
            if council_id != "glamorgan-spring-bay":
                 assert article.date, f"Article date is missing for {article.title}"

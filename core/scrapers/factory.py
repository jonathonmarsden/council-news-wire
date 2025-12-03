"""
Factory for creating scraper instances.
"""

from typing import Dict, Optional

from .base import BaseScraper
from .card import CardScraper
from .rss import RSSScraper
from .custom import InnerWestScraper

class ScraperFactory:
    """Factory for creating scraper instances."""
    
    @staticmethod
    def create_scraper(council: Dict, proxy: Optional[str] = None) -> BaseScraper:
        """
        Create a scraper instance based on council configuration.
        
        Args:
            council: Council configuration dictionary
            proxy: Optional proxy URL to override config
            
        Returns:
            Configured scraper instance
        """
        scraper_type = council.get('scraper', 'card_scraper')
        use_curl = scraper_type == 'curl_scraper' or council.get('use_curl', False)
        mobile_mode = council.get('mobile_mode', False)
        limit = council.get('limit')
        
        selectors = {
            'item_selector': council.get('item_selector'),
            'title_selector': council.get('title_selector'),
            'link_selector': council.get('link_selector'),
            'date_selector': council.get('date_selector'),
            'content_selector': council.get('content_selector'),
            'excerpt_selector': council.get('excerpt_selector')
        }
        
        # Registry of custom scrapers
        scraper_classes = {
            'inner_west_scraper': InnerWestScraper,
            'card_scraper': CardScraper,
            'curl_scraper': CardScraper, # curl_scraper is just CardScraper with use_curl=True
            'rss_scraper': RSSScraper,
        }
        
        scraper_class = scraper_classes.get(scraper_type, CardScraper)
        
        # Use CLI proxy if provided, otherwise check council config
        use_proxy = proxy or council.get('proxy')
        
        # Get impersonation setting (default to chrome110)
        impersonate = council.get('impersonate', 'chrome110')
        
        return scraper_class(
            council_id=council['id'],
            council_name=council['name'],
            news_url=council['news_url'],
            use_curl=use_curl,
            mobile_mode=mobile_mode,
            selectors=selectors,
            limit=limit,
            proxy=use_proxy,
            impersonate=impersonate
        )

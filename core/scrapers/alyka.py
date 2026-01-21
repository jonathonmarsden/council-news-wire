import json
from typing import List, Dict, Optional
from .base import BaseScraper, NewsArticle

class AlykaScraper(BaseScraper):
    """
    Scraper for Alyka/Kentico CMS sites (e.g. Stirling, Swan, Rockingham).
    These sites typically use a JSON API for search results/news listings.
    """
    
    def __init__(self, council_id: str, council_name: str, news_url: str, **kwargs):
        # Extract configuration from kwargs before calling super
        self.api_endpoint = kwargs.pop('aliased_endpoint', None) or kwargs.pop('api_url', None)
        self.node_alias_path = kwargs.pop('node_alias_path', '/city-and-council/news')
        self.news_index = kwargs.pop('news_index', 'News')
        self.class_name = kwargs.pop('class_name', 'AWPT.News')
        
        # Remove selectors from kwargs as they aren't used for the API call directly
        kwargs.pop('selectors', None)
        
        super().__init__(council_id, council_name, news_url, **kwargs)
        
        # Default endpoint logic
        if not self.api_endpoint:
            if 'stirling' in council_id:
                self.api_endpoint = "https://www.stirling.wa.gov.au/ksearchnews/ksearchresult"

    def scrape(self) -> List[NewsArticle]:
        if not self.api_endpoint:
            print(f"[{self.council_id}] Error: No API endpoint configured for AlykaScraper")
            return []

        # Construct SearchParam
        # This structure seems specific to the "KSearch" module used by these councils
        search_param = [
            {"key": "classname", "values": [self.class_name], "or": "true", "operator": "eq"},
            {"key": "searchindexes", "values": [self.news_index], "or": "true", "operator": "eq"},
            {"key": "nodealiaspath", "values": [self.node_alias_path], "or": "true", "operator": "eq"}
        ]
        
        # SearchFilter
        search_filter = [
            {"key": "Sort", "values": ["ArticleReleaseDate DESC"], "or": False, "operator": ""}
        ]
        
        # Body
        body = {
            "take": self.limit or 20,
            "skip": 0,
            "page": 1,
            "pageSize": self.limit or 20
        }
        
        # Headers
        # Note: Origin and Referer might need to be dynamic based on the news_url domain
        from urllib.parse import urlparse
        parsed_url = urlparse(self.news_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        headers = {
            "Content-Type": "application/json",
            "SearchParam": json.dumps(search_param),
            "SearchFilter": json.dumps(search_filter),
            "Referer": self.news_url,
            "Origin": base_url
        }
        
        try:
            # Import requests from curl_cffi to handle potential WAFs
            from curl_cffi import requests
            
            response = requests.post(
                self.api_endpoint, 
                json=body, 
                headers=headers, 
                impersonate=self.impersonate or "chrome110",
                proxies={"http": self.proxy, "https": self.proxy} if self.proxy else None,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"[{self.council_id}] API failed with status {response.status_code}")
                # Optional: print response text if debug mode?
                return []
                
            data = response.json()
            articles = []
            
            # The 'Data' key seems standard for this API response
            for item in data.get('Data', []):
                title = item.get('ArticleTitle')
                date_str = item.get('ArticleReleaseDate')
                summary = item.get('ArticleSummary')
                page_url = item.get('PageUrl')
                
                if not title or not page_url:
                    continue
                    
                url = self.make_absolute_url(page_url)
                date = self.parse_date(date_str)
                
                article = self.create_article(title, url, date, summary)
                articles.append(article)
                
            return articles
            
        except Exception as e:
            print(f"[{self.council_id}] Error scraping: {e}")
            return []

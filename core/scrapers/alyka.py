import json
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from .base import BaseScraper, NewsArticle
from core.exceptions import ScrapeError

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
        
        # Extended params for HTML Result mode
        self.transformation_name = kwargs.pop('transformationname', None)
        self.header_transformation = kwargs.pop('headertransformationname', None)
        self.footer_transformation = kwargs.pop('footertransformationname', None)
        
        # Extract selectors if provided
        selectors = kwargs.pop('selectors', {})
        self.item_selector = selectors.get('item_selector')
        self.title_selector = selectors.get('title_selector')
        self.link_selector = selectors.get('link_selector')
        self.date_selector = selectors.get('date_selector')
        self.excerpt_selector = selectors.get('excerpt_selector') or selectors.get('exporter_selector')
        
        super().__init__(council_id, council_name, news_url, **kwargs)
        
        # Default endpoint logic
        if not self.api_endpoint:
            if 'stirling' in council_id:
                self.api_endpoint = "https://www.stirling.wa.gov.au/ksearchnews/ksearchresult"

    def scrape(self) -> List[NewsArticle]:
        if not self.api_endpoint:
            print(f"[{self.council_id}] Error: No API endpoint configured for AlykaScraper")
            return []

        if "htmlresult" in self.api_endpoint.lower():
            return self.scrape_html_result()
        else:
            return self.scrape_ksearch_result()

    def scrape_html_result(self) -> List[NewsArticle]:
        """
        Handles the 'htmlresult' endpoint (e.g. City of Swan).
        Returns a JSON with 'htmlResult' string containing the rendered items.
        """
        # Headers
        parsed_url = urlparse(self.news_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        headers = {
            "Content-Type": "application/json",
            "Origin": base_url,
            "Referer": self.news_url,
             # Common user agent handled by impersonate, but good to ensure
        }
        
        # Construct PR (Parameters)
        pr = []
        if self.transformation_name:
            pr.append({"key": "transformationname", "values": [{"value": self.transformation_name}]})
        if self.header_transformation:
            pr.append({"key": "headertransformationname", "values": [{"value": self.header_transformation}]})
        if self.footer_transformation:
            pr.append({"key": "footertransformationname", "values": [{"value": self.footer_transformation}]})
        
        # Standard PR fields
        pr.append({"key": "classname", "values": [{"value": self.class_name}]})
        pr.append({"key": "searchindexes", "values": [{"value": self.news_index}]})
        pr.append({"key": "nodealiaspath", "values": [{"value": self.node_alias_path}]})
        
        body = {
            "SI": self.news_index,
            "OB": "ArticleReleaseDate desc",
            "Q": "",
            "PS": self.limit or 20,
            "FS": self.limit or 20,
            "PG": 1,
            "PR": pr,
            "IncludeFirst": False
        }
        
        try:
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
                raise ScrapeError(
                    f"{self.council_id}: Alyka API failed with HTTP {response.status_code}"
                )

            data = response.json()
        except ScrapeError:
            raise
        except Exception as e:
            print(f"[{self.council_id}] Error in scrape_html_result: {e}")
            raise ScrapeError(f"{self.council_id}: Alyka API fetch/parse failed: {e}") from e

        html_content = data.get('htmlResult', '')

        if not html_content:
            return []

        return self.parse_html_content(html_content)

    def parse_html_content(self, html: str) -> List[NewsArticle]:
        """
        Parses the HTML returned by the API.
        Uses the configured selectors if available, or defaults.
        """
        soup = BeautifulSoup(html, 'html.parser')
        articles = []
        
        # Use configured item_selector or default to 'div.col'
        selector = self.item_selector or 'article'
        items = soup.select(selector)
        
        if not items and 'col' in selector:
             # Fallback
             items = soup.select('div[data-ty="SmartSearchItem"]')
        
        for item in items:
            try:
                # Title
                title = None
                if self.title_selector:
                    title_elem = item.select_one(self.title_selector)
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                
                # If no title selector or not found, try common
                if not title:
                     title_elem = item.select_one('h3, h4, .hotbox-content h3')
                     if title_elem:
                         title = title_elem.get_text(strip=True)

                # Link
                url = None
                if self.link_selector:
                    link_elem = item.select_one(self.link_selector)
                    if link_elem:
                        url = link_elem.get('href')
                
                if not url:
                     link_elem = item.select_one('a')
                     if link_elem:
                         url = link_elem.get('href')

                # Date
                date = None
                if self.date_selector:
                    date_elem = item.select_one(self.date_selector)
                    if date_elem:
                        date = self.parse_date(date_elem.get_text(strip=True))

                # Excerpt
                excerpt = None
                if self.excerpt_selector:
                    excerpt_elem = item.select_one(self.excerpt_selector)
                    if excerpt_elem:
                        excerpt = excerpt_elem.get_text(strip=True)

                if title and url:
                    full_url = self.make_absolute_url(url)
                    article = self.create_article(title, full_url, date, excerpt)
                    articles.append(article)
            except Exception as e:
                print(f"[{self.council_id}] Error parsing item: {e}")
                continue
                
        return articles

    def scrape_ksearch_result(self) -> List[NewsArticle]:
        search_param = [
            {"key": "classname", "values": [self.class_name], "or": "true", "operator": "eq"},
            {"key": "searchindexes", "values": [self.news_index], "or": "true", "operator": "eq"},
            {"key": "nodealiaspath", "values": [self.node_alias_path], "or": "true", "operator": "eq"}
        ]
        
        search_filter = [
            {"key": "Sort", "values": ["ArticleReleaseDate DESC"], "or": False, "operator": ""}
        ]
        
        body = {
            "take": self.limit or 20,
            "skip": 0,
            "page": 1,
            "pageSize": self.limit or 20
        }
        
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
                raise ScrapeError(
                    f"{self.council_id}: Alyka ksearch API failed with HTTP {response.status_code}"
                )

            data = response.json()
        except ScrapeError:
            raise
        except Exception as e:
            print(f"[{self.council_id}] Error scraping: {e}")
            raise ScrapeError(f"{self.council_id}: Alyka ksearch fetch/parse failed: {e}") from e

        articles = []

        for item in data.get('Data', []):
            try:
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
            except Exception as e:
                print(f"[{self.council_id}] Error scraping: {e}")
                continue

        return articles

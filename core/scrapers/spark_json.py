from typing import List, Optional, Dict, Any
from datetime import datetime
from dateutil import parser as date_parser
from urllib.parse import urljoin
import requests

from .base import BaseScraper, NewsArticle
from core.exceptions import ScrapeError

class SparkNewsListingScraper(BaseScraper):
    """
    Scraper for SparkCMS / Catalyst 'NewsListing' API.
    Used by Mandurah (and possibly others) requiring a UUID.
    """

    def __init__(self, council_id: str, council_name: str, news_url: str,
                 listing_id: str = None,
                 **kwargs):
        super().__init__(council_id, council_name, news_url, **kwargs)
        self.listing_id = listing_id

    def scrape(self) -> List[NewsArticle]:
        if not self.listing_id:
            print(f"[{self.council_name}] Error: 'listing_id' is required for SparkNewsListingScraper.")
            return []

        # Construct API URL. Often it's at root /api/NewsListing/
        # But news_url might be /explore/whats-on/news. 
        # We should use the domain root.
        
        # parse the news_url to get base
        from urllib.parse import urlparse
        parsed = urlparse(self.news_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        api_url = urljoin(base_url, "/api/NewsListing/")
        
        params = {
            "Id": self.listing_id,
            "CurrentPage": 0,
            "PageSize": 20
        }
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest"
            }

            # Using standard requests for now as this is a JSON API
            response = requests.get(
                api_url,
                params=params,
                headers=headers,
                timeout=30,
                proxies={'http': self.proxy, 'https': self.proxy} if self.proxy else None
            )
            response.raise_for_status()
            data = response.json()
        except ScrapeError:
            raise
        except (requests.RequestException, ValueError) as e:
            print(f"[{self.council_name}] Error scraping Spark API: {e}")
            raise ScrapeError(f"{self.council_id}: Spark API fetch/parse failed: {e}") from e

        articles = []
        if "NewsItems" in data:
            for item in data["NewsItems"]:
                try:
                    # Item structure: {"Title": "...", "Summary": "...", "ArticleDate": "...", "Url": "..."}
                    title = item.get("Title")
                    summary = item.get("Summary")
                    date_str = item.get("ArticleDate")
                    rel_url = item.get("Url")

                    if not title or not rel_url:
                        continue

                    full_url = urljoin(base_url, rel_url)
                    date = None
                    if date_str:
                        try:
                            # Handle ISO format with timezone
                            date = date_parser.isoparse(date_str)
                            # Ensure naive/aware consistency if needed, but BaseScraper usually handles whatever
                            if date.tzinfo:
                                date = date.replace(tzinfo=None) # naive UTC or local? Usually we want naive for simplicity or keep it.
                                # The base scraper expects naive or handles it?
                                # Let's keep it simple.
                        except Exception:
                            pass

                    articles.append(self.create_article(
                        title=title,
                        url=full_url,
                        date=date,
                        excerpt=summary or None
                    ))
                except Exception as e:
                    print(f"[{self.council_name}] Error scraping Spark API: {e}")
                    continue
        return articles

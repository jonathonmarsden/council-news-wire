from typing import List, Optional, Dict, Any
from datetime import datetime
from dateutil import parser as date_parser
import requests
from curl_cffi import requests as crequests

from .base import BaseScraper, NewsArticle

class JsonScraper(BaseScraper):
    """
    Generic scraper for JSON APIs.
    """

    def __init__(self, council_id: str, council_name: str, news_url: str,
                 item_selector: str = "items", # Key path to list
                 title_selector: str = "title",
                 date_selector: str = "date",
                 link_selector: str = "link", # Can be format string with {key}
                 description_selector: str = None,
                 **kwargs):
        super().__init__(council_id, council_name, news_url, **kwargs)
        self.item_selector = item_selector
        self.title_selector = title_selector
        self.date_selector = date_selector
        self.link_selector = link_selector
        self.description_selector = description_selector
        self.use_curl = kwargs.get('use_curl', False)
        
    def _get_nested(self, data: Dict, path: str):
        """Helper to get nested dictionary values using dot notation."""
        keys = path.split('.')
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    def scrape(self) -> List[NewsArticle]:
        try:
            print(f"[{self.council_name}] Fetching JSON from {self.news_url}")
            
            if self.use_curl:
                response = crequests.get(
                    self.news_url,
                    impersonate="chrome120",
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=30
                )
            else:
                response = requests.get(
                    self.news_url,
                    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                    timeout=30
                )
            
            if response.status_code != 200:
                print(f"[{self.council_name}] Failed to fetch JSON. Status: {response.status_code}")
                return []
                
            data = response.json()
            
            # Extract list of items
            items = self._get_nested(data, self.item_selector)
            if not items or not isinstance(items, list):
                print(f"[{self.council_name}] No items found with selector '{self.item_selector}'")
                return []
                
            print(f"[{self.council_name}] Found {len(items)} raw JSON items")
            
            seen_urls = set()
            articles = []
            
            for item in items:
                # Extract Title
                title = self._get_nested(item, self.title_selector)
                if not title:
                    continue
                    
                # Extract Link
                if "{" in self.link_selector and "}" in self.link_selector:
                    # Format string mode (e.g. "https://site.com/{slug}")
                    try:
                        # We need to flatten the item or use a custom formatter that handles dots? 
                        # Simple flat keys are safest for now, but let's try to support dots manually.
                        
                        # Quick hack: create a flat context for commonly needed keys or support the dot notation in format?
                        # Standard .format() doesn't like dots in keys unless accessed like {0.field}.
                        # Let's simple string replace for known patterns if needed, or better:
                        
                        link = self.link_selector
                        # Find all placeholders
                        import re
                        matches = re.findall(r'\{([^}]+)\}', link)
                        for match in matches:
                            val = self._get_nested(item, match)
                            if val:
                                link = link.replace(f"{{{match}}}", str(val))
                            else:
                                link = None # Failed to resolve placeholder
                                break
                                
                    except Exception as e:
                        print(f"Error formatting link: {e}")
                        link = None
                else:
                    link = self._get_nested(item, self.link_selector)
                    
                if not link:
                    continue
                    
                if link in seen_urls:
                    continue
                seen_urls.add(link)
                
                # Extract Date
                date_str = self._get_nested(item, self.date_selector)
                date = None
                if date_str:
                    try:
                        date = date_parser.parse(str(date_str))
                    except:
                        pass
                
                # Extract Description
                description = ""
                if self.description_selector:
                    description = self._get_nested(item, self.description_selector) or ""
                    
                articles.append(NewsArticle(
                    council_id=self.council_id,
                    council_name=self.council_name,
                    title=title.strip(),
                    url=link,
                    date=date,
                    excerpt=description
                ))
                
            return articles
            
        except Exception as e:
            print(f"[{self.council_name}] JSON Scraper Error: {e}")
            return []

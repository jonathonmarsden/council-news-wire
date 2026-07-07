"""
RSS feed scraper implementation.
"""

from typing import List, Optional, Dict
from urllib.parse import unquote
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .base import BaseScraper, NewsArticle

class RSSScraper(BaseScraper):
    """Scraper for RSS feeds."""
    
    def __init__(self, council_id: str, council_name: str, news_url: str, use_curl: bool = False, use_cloudscraper: bool = False, mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, limit: Optional[int] = None, proxy: Optional[str] = None, impersonate: str = "chrome110", **kwargs):
        super().__init__(council_id, council_name, news_url, use_curl, use_cloudscraper, mobile_mode, limit, proxy, impersonate, **kwargs)
        self.selectors = selectors or {}
    
    def scrape(self) -> List[NewsArticle]:
        content = self.fetch_page_or_raise(self.news_url)
            
        # Use 'xml' parser for RSS if available, else html.parser
        try:
            soup = BeautifulSoup(content, 'xml')
        except Exception:
            soup = BeautifulSoup(content, 'html.parser')
        articles = []
        
        items = soup.find_all('item')
        for item in items:
            title_elem = item.find('title')
            link_elem = item.find('link')
            url_elem = item.find('url')  # Fallback for some feeds like Georges River
            desc_elem = item.find('description')
            date_elem = item.find('pubDate')
            
            link = None
            if link_elem:
                link = link_elem.get_text(strip=True)
            elif url_elem:
                raw_url = url_elem.get_text(strip=True)
                # Check if URL is encoded (e.g. https%3a%2f%2f)
                if '%' in raw_url:
                    link = unquote(raw_url)
                else:
                    link = raw_url
            
            if not title_elem or not link:
                continue
                
            title = title_elem.get_text(strip=True)
            
            date = None
            if date_elem:
                try:
                    date = date_parser.parse(date_elem.get_text(strip=True))
                except Exception:
                    pass
            
            excerpt = None
            
            # Try content:encoded first (often has full content)
            content_encoded = item.find('content:encoded')
            bodytext = item.find('bodytext') # Fallback for Georges River
            
            if content_encoded:
                content_text = content_encoded.get_text(strip=True)
                if content_text:
                    content_soup = BeautifulSoup(content_text, 'html.parser')
                    # Try to find the first meaningful paragraph
                    for p in content_soup.find_all('p'):
                        text = p.get_text(strip=True)
                        # Skip short lines or boilerplate
                        if len(text) > 30 and "appeared first on" not in text:
                            excerpt = text[:280]
                            if len(text) > 280:
                                excerpt += "..."
                            break
            # Try bodytext (Georges River style)
            elif bodytext:
                body_text = bodytext.get_text(strip=True)
                # Cleanup "andnbsp;" and HTML entities often found in this field
                clean_body = body_text.replace('andnbsp;', ' ')
                if len(clean_body) > 30:
                     excerpt = clean_body[:280]
                     if len(clean_body) > 280:
                         excerpt += "..."

            # Fallback to description if no good excerpt found
            if not excerpt and desc_elem:
                desc_text = desc_elem.get_text(strip=True)
                # Remove HTML tags from description
                desc_soup = BeautifulSoup(desc_text, 'html.parser')
                clean_desc = desc_soup.get_text(strip=True)
                
                # Check for WordPress boilerplate
                if "appeared first on" not in clean_desc:
                    excerpt = clean_desc[:280]
                    if len(clean_desc) > 280:
                        excerpt += "..."
            
            articles.append(self.create_article(title, link, date, excerpt))
            
        return articles

from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from dateutil import parser as date_parser
import re

from .base import BaseScraper, NewsArticle

class WannerooScraper(BaseScraper):
    """
    Scraper for City of Wanneroo (Jadu CMS).
    """
    def __init__(self, council_id: str, council_name: str, news_url: str, 
                 use_curl: bool = False, use_cloudscraper: bool = False, 
                 mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, 
                 limit: Optional[int] = None, proxy: Optional[str] = None, 
                 impersonate: str = "chrome110"):
        super().__init__(council_id, council_name, news_url, use_curl, use_cloudscraper, 
                         mobile_mode, limit, proxy, impersonate)

    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page(self.news_url)
        if not html:
            return []
            
        soup = BeautifulSoup(html, 'html.parser')
        articles = []
        
        # Jadu structure for Wanneroo
        items = soup.select('a.item-list__article')
        
        for item in items:
            link_url = item.get('href')
            if not link_url:
                continue
            
            url = urljoin(self.news_url, link_url)
            
            title_tag = item.select_one('.box-header, h2, h3')
            if not title_tag:
                continue
            
            title = title_tag.get_text(strip=True)
            
            # Date: "Published on Tuesday, 20th January 2026"
            date = None
            date_tag = item.select_one('.subtext')
            if date_tag:
                date_text = date_tag.get_text(strip=True)
                # Clean up "Published on "
                clean_date = date_text.replace('Published on', '').strip()
                # Clean up ordinals
                clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', clean_date)
                try:
                    date = date_parser.parse(clean_date)
                except Exception:
                    pass
            
            article = NewsArticle(
                council_id=self.council_id,
                council_name=self.council_name,
                title=title,
                url=url,
                date=date,
                excerpt=""
            )
            articles.append(article)
            
        return articles

class PerthScraper(BaseScraper):
    """
    Scraper for City of Perth (Cloudflare protected).
    Requires curl_cffi impersonation.
    """
    def __init__(self, council_id: str, council_name: str, news_url: str, 
                 use_curl: bool = True, use_cloudscraper: bool = False, 
                 mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, 
                 limit: Optional[int] = None, proxy: Optional[str] = None, 
                 impersonate: str = "chrome110"):
        # Force use_curl=True and impersonate
        super().__init__(council_id, council_name, news_url, use_curl=True, use_cloudscraper=False, 
                         mobile_mode=mobile_mode, limit=limit, proxy=proxy, impersonate="chrome110")

    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page(self.news_url)
        if not html:
            return []
            
        soup = BeautifulSoup(html, 'html.parser')
        articles = []
        
        items = soup.select('.card-list__item')
        
        for item in items:
            title_tag = item.select_one('.card-list__title')
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            
            link_tag = item.select_one('a.card-list__whole-link')
            if not link_tag:
                # Fallback to any link
                link_tag = item.select_one('a')
            
            if not link_tag:
                continue
                
            link_url = link_tag.get('href')
            url = urljoin(self.news_url, link_url)
            
            date = None
            date_tag = item.select_one('.card-list__date')
            if date_tag:
                date_text = date_tag.get_text(strip=True)
                # Remove "- X min read"
                if '-' in date_text:
                    date_text = date_text.split('-')[0].strip()
                try:
                    date = date_parser.parse(date_text)
                except Exception:
                    pass
            
            excerpt = ""
            excerpt_tag = item.select_one('.card-list__synopsis')
            if excerpt_tag:
                excerpt = excerpt_tag.get_text(strip=True)
                
            article = NewsArticle(
                council_id=self.council_id,
                council_name=self.council_name,
                title=title,
                url=url,
                date=date,
                excerpt=excerpt
            )
            articles.append(article)
            
        return articles

class ClaremontScraper(BaseScraper):
    """
    Scraper for Town of Claremont.
    """
    def __init__(self, council_id: str, council_name: str, news_url: str, 
                 use_curl: bool = True, use_cloudscraper: bool = False, 
                 mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, 
                 limit: Optional[int] = None, proxy: Optional[str] = None, 
                 impersonate: str = "chrome110"):
        super().__init__(council_id, council_name, news_url, use_curl, use_cloudscraper, 
                         mobile_mode, limit, proxy, impersonate)

    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page(self.news_url)
        if not html:
            return []
            
        soup = BeautifulSoup(html, 'html.parser')
        articles = []
        
        # Select cards
        items = soup.select('.page-card')
        
        for item in items:
            # Title
            title_tag = item.select_one('h3')
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            
            # URL (item itself is the A tag)
            if item.name == 'a':
                link_url = item.get('href')
            else:
                a_tag = item.select_one('a')
                link_url = a_tag.get('href') if a_tag else None
                
            if not link_url:
                continue
            url = urljoin(self.news_url, link_url)
            
            # Date
            date = None
            date_tag = item.select_one('.news-card-details strong')
            if date_tag:
                date_text = date_tag.get_text(strip=True)
                try:
                    date = date_parser.parse(date_text)
                except Exception:
                    pass
            
            # Excerpt
            excerpt = ""
            
            article = NewsArticle(
                council_id=self.council_id,
                council_name=self.council_name,
                title=title,
                url=url,
                date=date,
                excerpt=excerpt
            )
            articles.append(article)
            
        return articles

class JoondalupScraper(BaseScraper):
    """
    Scraper for City of Joondalup (Kentico AJAX).
    """
    def __init__(self, council_id: str, council_name: str, news_url: str, 
                 use_curl: bool = True, use_cloudscraper: bool = False, 
                 mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, 
                 limit: Optional[int] = None, proxy: Optional[str] = None, 
                 impersonate: str = "chrome110"):
        super().__init__(council_id, council_name, news_url, use_curl, use_cloudscraper, 
                         mobile_mode, limit, proxy, impersonate)

    def scrape(self) -> List[NewsArticle]:
        # API URL
        api_url = "https://www.joondalup.wa.gov.au/search/htmlresult"
        
        # Construct Payload based on successful test
        pr_data = [
            {"key": "widgetclassname", "values": [{"value": "AWNewsSmartSearchListing"}]},
            {"key": "widgettemplatename", "values": [{"value": "AWNewsSmartSearchListing"}]},
            {"key": "transformationname", "values": [{"value": "AWPT.News.SmartSearchItem"}]},
            {"key": "headertransformationname", "values": [{"value": "AWPT.News.SmartSearchHeader"}]},
            {"key": "footertransformationname", "values": [{"value": "AWPT.News.SmartSearchFooter"}]},
            {"key": "classname", "values": [{"value": "AWPT.News"}]},
            {"key": "nodealiaspath", "values": [{"value": "/City-and-Council/Latest-news-updates"}]}
        ]

        payload = {
            "SI": "News",
            "OB": "",
            "Q": "",
            "PS": 12,
            "FS": 12,
            "PG": 1,
            "PR": pr_data,
            "IncludeFirst": False
        }
        
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Referer": self.news_url,
            "Origin": "https://www.joondalup.wa.gov.au",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        from curl_cffi import requests
        
        try:
            response = requests.post(
                api_url,
                json=payload,
                impersonate=self.impersonate,
                headers=headers,
                timeout=30,
                proxies={"http": self.proxy, "https": self.proxy} if self.proxy else None
            )
            
            if response.status_code != 200:
                print(f"Joondalup API failed: {response.status_code}")
                return []
                
            data = response.json()
            html_content = data.get("htmlResult", "")
            
            if not html_content:
                return []
                
            soup = BeautifulSoup(html_content, 'html.parser')
            articles = []
            
            # Select items
            items = soup.select('article.card')
            
            for item in items:
                link_tag = item.select_one('a.hotbox')
                if not link_tag:
                    continue
                
                link_url = link_tag.get('href')
                url = urljoin("https://www.joondalup.wa.gov.au", link_url)
                
                title = ""
                heading = item.select_one('h3, h4, .title, .hotbox-content h3')
                if heading:
                    title = heading.get_text(strip=True)
                elif link_tag.get('aria-label'):
                    aria = link_tag.get('aria-label')
                    if "News Date:" in aria:
                        title = aria.split("News Date:")[0].strip()
                    else:
                        title = aria
                
                if not title:
                    title = "No Title"

                date = None
                date_str = item.get('data-datetime')
                if date_str:
                    try:
                        date = date_parser.parse(date_str)
                    except:
                        pass
                
                article = NewsArticle(
                    council_id=self.council_id,
                    council_name=self.council_name,
                    title=title,
                    url=url,
                    date=date,
                    excerpt=""
                )
                articles.append(article)
                
            return articles
            
        except Exception as e:
            print(f"Error scraping Joondalup: {e}")
            return []

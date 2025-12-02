"""
Base scraper class for council news pages.

Provides common functionality for scraping news articles from Victorian council websites.
"""

import re
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False


@dataclass
class NewsArticle:
    """Represents a news article from a council website."""
    
    council_id: str
    council_name: str
    title: str
    url: str
    date: Optional[datetime] = None
    excerpt: Optional[str] = None
    
    @property
    def unique_id(self) -> str:
        """Generate a unique identifier for this article."""
        return self.url
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'council_id': self.council_id,
            'council_name': self.council_name,
            'title': self.title,
            'url': self.url,
            'date': self.date.isoformat() if self.date else None,
            'excerpt': self.excerpt
        }


class BaseScraper(ABC):
    """Base class for council news scrapers."""
    
    # Common headers to mimic a browser
    # Note: Using 'gzip, deflate' only - 'br' (brotli) requires extra library
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-AU,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    def __init__(self, council_id: str, council_name: str, news_url: str, use_curl: bool = False, mobile_mode: bool = False, limit: Optional[int] = None, proxy: Optional[str] = None):
        """
        Initialize the scraper.
        
        Args:
            council_id: Unique identifier for the council (kebab-case)
            council_name: Human-readable council name
            news_url: URL of the council's news page
            use_curl: Whether to use curl for WAF bypass
            mobile_mode: Whether to impersonate a mobile device (iPhone)
            limit: Maximum number of articles to scrape
            proxy: Proxy URL (e.g. http://user:pass@host:port)
        """
        self.council_id = council_id
        self.council_name = council_name
        self.news_url = news_url
        self.use_curl = use_curl
        self.mobile_mode = mobile_mode
        self.limit = limit
        self.proxy = proxy
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        
        # Don't set proxies immediately - we'll try direct first in fetch_page
        # unless we decide otherwise later.
    
    def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch a web page, handling WAF protection if needed.
        Try direct connection first, then fallback to proxy if configured.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string, or None if fetch failed
        """
        # 1. Try Direct First
        # Clear proxies for direct attempt
        self.session.proxies = {}
        
        content = None
        if self.use_curl:
            content = self._fetch_with_curl(url, use_proxy=False)
        else:
            content = self._fetch_with_requests(url)
            
        if content:
            return content
            
        # 2. Fallback to Proxy
        if self.proxy:
            print(f"Direct fetch failed for {url}, retrying with proxy...")
            self.session.proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
            
            if self.use_curl:
                return self._fetch_with_curl(url, use_proxy=True)
            else:
                return self._fetch_with_requests(url)
                
        return None
    
    def _fetch_with_requests(self, url: str) -> Optional[str]:
        """Fetch page using requests library."""
        try:
            response = self.session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            # Only print error if we're not going to retry or if it's a proxy failure
            if self.session.proxies:
                print(f"Error fetching {url} (with proxy): {e}")
            else:
                # Don't spam logs for direct failures if we have a proxy fallback
                if not self.proxy:
                    print(f"Error fetching {url}: {e}")
            return None
    
    def _fetch_with_curl(self, url: str, use_proxy: bool = False) -> Optional[str]:
        """Fetch page using curl for WAF bypass."""
        print(f"DEBUG: Fetching with curl (Proxy: {use_proxy}): {url}")
        
        if CURL_CFFI_AVAILABLE:
            try:
                proxies = None
                if use_proxy and self.proxy:
                    proxies = {"http": self.proxy, "https": self.proxy}
                
                # Use chrome impersonation by default
                impersonate = "chrome"
                
                response = curl_requests.get(
                    url, 
                    impersonate=impersonate, 
                    proxies=proxies, 
                    timeout=60
                )
                
                if response.status_code == 200:
                    print(f"DEBUG: curl_cffi success, length: {len(response.text)}")
                    return response.text
                else:
                    print(f"DEBUG: curl_cffi failed with status {response.status_code}")
            except Exception as e:
                print(f"DEBUG: curl_cffi exception: {e}")
                # Fallback to subprocess curl if curl_cffi fails
        
        try:
            # Try simple curl first (often works better than spoofed headers for Akamai)
            cmd = [
                'curl', '-s', '-L',
                # '-A', self.HEADERS['User-Agent'],
                # '-H', f"Accept: {self.HEADERS['Accept']}",
                # '-H', f"Accept-Language: {self.HEADERS['Accept-Language']}",
                '--connect-timeout', '30',
                '--max-time', '60'
            ]
            
            if self.mobile_mode:
                cmd.extend([
                    '-A', 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                    '--http1.1'
                ])
            
            if use_proxy and self.proxy:
                cmd.extend(['--proxy', self.proxy])
                
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=90
            )
            if result.returncode == 0 and result.stdout:
                print(f"DEBUG: Curl success, length: {len(result.stdout)}")
                if len(result.stdout) < 1000:
                    print(f"DEBUG: Short content: {result.stdout}")
                return result.stdout
            print(f"Curl error for {url}: {result.stderr}")
            return None
        except subprocess.TimeoutExpired:
            print(f"Curl timeout for {url}")
            return None
        except Exception as e:
            print(f"Curl exception for {url}: {e}")
            return None
    
    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content into BeautifulSoup object."""
        return BeautifulSoup(html, 'html.parser')
    
    def make_absolute_url(self, url: str) -> str:
        """Convert relative URL to absolute URL."""
        if url.startswith('http'):
            return url
        return urljoin(self.news_url, url)
    
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse a date string into a datetime object.
        
        Handles various formats:
        - "28 Nov 2025"
        - "28 November 2025"
        - "Thu 28 Nov 2025"
        - "Published 28 Nov 2025"
        - "Updated Wed 26 Nov 2025"
        """
        if not date_str:
            return None
        
        # Clean up common prefixes
        date_str = re.sub(r'^(Published|Updated|Posted|Last updated|News|Media Release)( on)?[:\s/|-]*', '', date_str, flags=re.IGNORECASE)
        date_str = date_str.strip()
        
        try:
            return date_parser.parse(date_str, dayfirst=True)
        except (ValueError, TypeError):
            # Try fuzzy parsing as a fallback
            try:
                return date_parser.parse(date_str, dayfirst=True, fuzzy=True)
            except (ValueError, TypeError):
                return None
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if text is None:
            return ""
            
        if not isinstance(text, str):
            return str(text)

        # Fix common mojibake (UTF-8 bytes interpreted as Windows-1252/Latin-1)
        replacements = {
            'â': "'",
            'â\x80\x99': "'",
            'â': "-",
            'â\x80\x93': "-",
            'â': "-",
            'â\x80\x94': "-",
            'â': '"',
            'â\x80\x9c': '"',
            'â': '"',
            'â\x80\x9d': '"',
            'â¦': '...',
            'â\x80\xa6': '...',
            'Â': '',  # Non-breaking space artifact
            '\xa0': ' ', # Non-breaking space
        }
        
        for bad, good in replacements.items():
            if text:
                text = text.replace(bad, good)
            
        # Normalize whitespace
        if text:
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
        return ""
    
    @abstractmethod
    def scrape(self) -> List[NewsArticle]:
        """
        Scrape news articles from the council website.
        
        Returns:
            List of NewsArticle objects
        """
        pass
    
    def create_article(
        self,
        title: str,
        url: str,
        date: Optional[datetime] = None,
        excerpt: Optional[str] = None
    ) -> NewsArticle:
        """
        Create a NewsArticle with this scraper's council info.
        
        Args:
            title: Article title
            url: Article URL (will be made absolute)
            date: Publication date
            excerpt: Article excerpt/summary
            
        Returns:
            NewsArticle object
        """
        return NewsArticle(
            council_id=self.council_id,
            council_name=self.council_name,
            title=self.clean_text(title),
            url=self.make_absolute_url(url),
            date=date,
            excerpt=self.clean_text(excerpt) if excerpt else None
        )


class CardScraper(BaseScraper):
    """
    Generic scraper for card-based news layouts.
    
    Most Victorian council websites use a similar pattern:
    - News items displayed as cards in a list/grid
    - Each card has title, date, excerpt, and link
    - Pagination via ?page=N query parameter
    
    This scraper can be configured for different HTML structures
    by overriding the selector methods.
    """
    
    # CSS selectors - override these in subclasses for different structures
    # Note: Some sites wrap entire cards in <a> tags (e.g., a.card--news, a.card__news-listing)
    # Note: div.card with a > .card__title is common GovCMS pattern (Golden Plains, etc)
    # Note: .article-item with a.article-link is Webflow pattern (East Gippsland, etc)
    # Note: .media-item with a.media-link is Webflow pattern (Wellington, etc)
    # Note: article.news-item is Greater Shepparton pattern (use specific class to avoid generic articles)
    # Note: article.listing is Cardinia pattern (listing__heading + listing__summary)
    # Note: a.cont-item-news is Greater Geelong pattern
    # Note: .card-medium is Melbourne City Council pattern
    # Note: .i-tile is Port Phillip pattern
    # Note: .list-item-container is Darebin pattern
    ARTICLE_SELECTOR = 'article.news-item, article.listing, .news-card, .listing-item, .views-row, .content-card, .article-container, .media-item, a.card--news, a.card__news-listing, a.card[href*="/news/"], div.card, .article-item, a.cont-item-news, .card-medium, .i-tile, .list-item-container, a.card-y'
    TITLE_SELECTOR = 'h2 a, h3 a, .title a, a.title, .field--name-title a, .news-title a, a[href*="/news/"]'
    DATE_SELECTOR = '.date, .published, time, .meta-date, .field--name-created, .news-date, .card__meta'
    EXCERPT_SELECTOR = '.card__description, .excerpt, .summary, .description, .field--name-body, .teaser, p'
    
    def __init__(self, council_id: str, council_name: str, news_url: str, use_curl: bool = False, mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, limit: Optional[int] = None, proxy: Optional[str] = None):
        super().__init__(council_id, council_name, news_url, use_curl, mobile_mode, limit, proxy)
        self.selectors = selectors or {}

    def _get_clean_title(self, element) -> str:
        """Extract title text from an element, excluding date/metadata elements."""
        if not element:
            return ""
            
        # If element has no children (just text), return it
        if not hasattr(element, 'children'):
            # Ensure we use a separator if it's a Tag that somehow got here
            if hasattr(element, 'get_text'):
                return element.get_text(" ", strip=True)
            return str(element).strip()
            
        text_parts = []
        for child in element.children:
            if child.name:
                # Check classes
                classes = child.get('class', [])
                if isinstance(classes, list):
                    classes_str = ' '.join(classes)
                else:
                    classes_str = str(classes)
                
                # Skip known metadata elements
                # 'label' is used by Warren Shire for date
                # 'date', 'time', 'published' are common
                if any(c in classes_str for c in ['date', 'published', 'time', 'meta', 'label', 'right']):
                    continue
                if child.name == 'time':
                    continue
                    
                # Recursively get text from child
                text_parts.append(child.get_text(" ", strip=True))
            elif child.string:
                text_parts.append(child.string.strip())
                
        return " ".join(filter(None, text_parts))

    def _clean_excerpt(self, excerpt: str, title: str) -> Optional[str]:
        """Clean excerpt by removing title if it's duplicated."""
        if not excerpt or not title:
            return excerpt
            
        # Normalize for comparison
        excerpt_clean = excerpt.strip()
        title_clean = title.strip()
        
        # Check for exact match or title + ellipsis
        if excerpt_clean == title_clean:
            return None
        if excerpt_clean == title_clean + "...":
            return None
            
        # Check if excerpt starts with title
        if excerpt_clean.startswith(title_clean):
            # Remove title
            cleaned = excerpt_clean[len(title_clean):].strip()
            
            # Remove common separators at the start
            cleaned = re.sub(r'^[-:–—]\s*', '', cleaned).strip()
            
            # If what remains is just punctuation (like ...), return None
            if not cleaned or cleaned in ["...", ".", "-", ":"]:
                return None
            return cleaned
            
        return excerpt

    def scrape(self) -> List[NewsArticle]:
        """Scrape news articles from the news page."""
        articles = []
        
        html = self.fetch_page(self.news_url)
        if not html:
            return articles
        
        soup = self.parse_html(html)
        
        # First try structured article elements
        # Use configured selector if available, otherwise use default list
        article_selector = self.selectors.get('item_selector') or self.ARTICLE_SELECTOR
        
        for item in soup.select(article_selector):
            if self.limit and len(articles) >= self.limit:
                break
            article = self._parse_article(item)
            if article:
                articles.append(article)
        
        # If no articles found, try finding news links directly
        if not articles:
            articles = self._scrape_links_directly(soup)
            if self.limit:
                articles = articles[:self.limit]
            
        # If we have articles but missing dates, and a date_selector is configured,
        # try fetching the detail page to find the date.
        # This handles sites where the date is only on the detail page (e.g. Geelong, Melbourne).
        if self.selectors.get('date_selector'):
            # Limit to first 10 to avoid excessive requests
            for article in articles[:10]:
                if not article.date:
                    self._fetch_article_details(article)
                    # Be polite
                    time.sleep(0.2)
        
        return articles
    
    def _fetch_article_details(self, article: NewsArticle):
        """Fetch article page to find the date."""
        try:
            html = self.fetch_page(article.url)
            if not html:
                return
                
            soup = self.parse_html(html)
            
            # Try configured date_selector
            date_selector = self.selectors.get('date_selector')
            if date_selector:
                date_elem = soup.select_one(date_selector)
                if date_elem:
                    # Handle meta tags
                    if date_elem.name == 'meta' and date_elem.has_attr('content'):
                        text = date_elem['content']
                    else:
                        text = date_elem.get_text(strip=True)
                    
                    # Remove common prefixes
                    text = re.sub(r'^(Published|Date|Posted|Updated):\s*', '', text, flags=re.IGNORECASE)
                    article.date = self.parse_date(text)
        except Exception as e:
            print(f"Error fetching details for {article.url}: {e}")

    def _scrape_links_directly(self, soup) -> List[NewsArticle]:
        """
        Fallback scraper that looks for news links directly.
        
        Looks for links that match common news URL patterns.
        """
        articles = []
        seen_urls = set()
        
        # Common news URL patterns
        news_patterns = ['/news/', '/media-release', '/latest-news/', '/newsroom/']
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = self._get_clean_title(link)
            
            # Skip if no text or too short (but allow longer titles)
            if not text or len(text) < 15:
                continue
            
            # Skip if text looks like a date only
            if re.match(r'^(Published|Updated)?\s*\d', text):
                continue
            
            # Check if URL matches news patterns
            if not any(pattern in href.lower() for pattern in news_patterns):
                continue
            
            # Skip mailto links
            if href.startswith('mailto:'):
                continue
            
            # Skip pagination, category, and tag links
            if '?page=' in href or '/category/' in href or '/tag/' in href:
                continue
            
            # Skip links that are just the news index
            if href.rstrip('/').endswith('/news'):
                continue
            
            # Skip category pages (e.g., /news/20026/news_and_events - has /news/NNNNN/ but no /article/)
            if re.search(r'/news/\d+/', href) and '/article/' not in href:
                continue
            
            url = self.make_absolute_url(href)
            
            # Skip duplicates
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Try to find date near the link
            date = None
            
            # 1. Check inside the link itself (e.g. Warren Shire)
            link_text_full = link.get_text(" ", strip=True)
            date_match = re.search(
                r'(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4})',
                link_text_full
            )
            if date_match:
                date_str = date_match.group(1)
                date = self.parse_date(date_str)
                
                # Extra cleanup: If the title ends with this date, strip it
                # This handles cases where _get_clean_title failed to exclude the date element
                # or where the date is concatenated directly (e.g. "TitleDate")
                if text.endswith(date_str):
                    text = text[:-len(date_str)].strip()
                elif text.endswith(date_str.replace(" ", "")):
                     text = text[:-len(date_str.replace(" ", ""))].strip()
            
            # 2. Check parent/siblings if not found
            if not date:
                parent = link.find_parent()
                if parent:
                    # Look for date text in parent or siblings
                    # Be careful if parent has multiple links (likely a list container)
                    links_in_parent = parent.find_all('a', recursive=False)
                    if len(links_in_parent) <= 1:
                        date_text = parent.get_text()
                        date_match = re.search(
                            r'(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4})',
                            date_text
                        )
                        if date_match:
                            date = self.parse_date(date_match.group(1))
            
            article = self.create_article(text, url, date)
            articles.append(article)
        
        return articles
    
    def _parse_article(self, item) -> Optional[NewsArticle]:
        """Parse a single article item from the page."""
        title = None
        url = None
        date = None
        excerpt = None
        
        # Strategy -1: Configured selectors
        if self.selectors:
            # Link
            link_selector = self.selectors.get('link_selector')
            if link_selector:
                if link_selector == 'self' or link_selector == 'this':
                    link_elem = item if item.name == 'a' else None
                else:
                    link_elem = item.select_one(link_selector)
                
                if link_elem:
                    url = link_elem.get('href', '')
            
            # Title
            title_selector = self.selectors.get('title_selector')
            if title_selector:
                title_elem = item.select_one(title_selector)
                if title_elem:
                    title = self._get_clean_title(title_elem)
            
            # Date
            date_selector = self.selectors.get('date_selector')
            if date_selector:
                date_elem = item.select_one(date_selector)
                if date_elem:
                    date_text = date_elem.get_text(" ", strip=True)
                    date = self.parse_date(date_text)
            
            # Excerpt (optional)
            excerpt_selector = self.selectors.get('content_selector') # Using content_selector as excerpt for now
            if excerpt_selector:
                excerpt_elem = item.select_one(excerpt_selector)
                if excerpt_elem:
                    raw_excerpt = excerpt_elem.get_text(" ", strip=True)
                    excerpt = self._clean_excerpt(raw_excerpt, title)
            
            if title and url:
                return self.create_article(title, url, date, excerpt)

        # Strategy 0: Card div with link inside containing .card__title (Golden Plains/GovCMS pattern)
        # Structure: div.card > a > div.card__title > h2
        # Note: Requires date element to filter out promotional cards (e.g., "GB news and magazine")
        if item.name == 'div' and 'card' in item.get('class', []):
            card_link = item.select_one('a[href*="/news/"], a[href*="/news-and-media/"]')
            if card_link:
                url = card_link.get('href', '')
                # Look for title in card__title div
                title_elem = item.select_one('.card__title h2, .card__title h3, .card__title')
                if title_elem:
                    title = self._get_clean_title(title_elem)
                    # Get date from card__date or time element - REQUIRED for news articles
                    date_elem = item.select_one('.card__date time, .card__date, time[datetime]')
                    if date_elem:
                        datetime_attr = date_elem.get('datetime')
                        if datetime_attr:
                            date = self.parse_date(datetime_attr)
                        else:
                            date = self.parse_date(date_elem.get_text(strip=True))
                        # Get excerpt from card__desc if present
                        excerpt_elem = item.select_one('.card__excerpt, .card__summary, .card__description, .card__desc')
                        if excerpt_elem:
                            excerpt = excerpt_elem.get_text(strip=True)
                        # Only return if we have date (filters out promo cards like "GB news and magazine")
                        if title and url and len(title) >= 10:
                            return self.create_article(title, url, date, excerpt)
        
        # Strategy 0a: Webflow article-item pattern (East Gippsland, etc)
        # Structure: div.article-item > a.article-link > div.article-inner > h4 (title)
        if item.name == 'div' and 'article-item' in item.get('class', []):
            article_link = item.select_one('a.article-link')
            if article_link:
                url = article_link.get('href', '')
                # Title is in h4 or h3
                title_elem = item.select_one('h4, h3, h2')
                if title_elem:
                    title = self._get_clean_title(title_elem)
                    # Date is in .small-text before the title (often with .teal.caps class)
                    date_elem = item.select_one('.small-text.teal, .small-text.caps, .article-date')
                    if date_elem:
                        date = self.parse_date(date_elem.get_text(strip=True))
                    # Excerpt is in .article-body-wrap or similar
                    excerpt_elem = item.select_one('.article-body-wrap .small-text, .article-body-wrap, .article-excerpt')
                    if excerpt_elem:
                        excerpt = excerpt_elem.get_text(strip=True)
                    if title and url and len(title) >= 10:
                        return self.create_article(title, url, date, excerpt)
        
        # Strategy 0b: Webflow media-item pattern (Wellington, etc)
        # Structure: div.media-item > a.media-link > .media-inner > .media-title
        if item.name == 'div' and 'media-item' in item.get('class', []):
            media_link = item.select_one('a.media-link')
            if media_link:
                url = media_link.get('href', '')
                # Title is in .media-title
                title_elem = item.select_one('.media-title')
                if title_elem:
                    title = self._get_clean_title(title_elem)
                    # Date is in .media-date
                    date_elem = item.select_one('.media-date')
                    if date_elem:
                        date = self.parse_date(date_elem.get_text(strip=True))
                    if title and url and len(title) >= 10:
                        return self.create_article(title, url, date, excerpt)
        
        # Strategy 0c: Greater Shepparton news-item pattern
        # Structure: article.news-item > a.news-item-link > .news-item-details > h1.news-item-heading
        if item.name == 'article' and 'news-item' in item.get('class', []):
            news_link = item.select_one('a.news-item-link')
            if news_link:
                url = news_link.get('href', '')
                # Title is in h1.news-item-heading
                title_elem = item.select_one('h1.news-item-heading, .news-item-heading')
                if title_elem:
                    title = self._get_clean_title(title_elem)
                    # Date is in time[datetime]
                    time_elem = item.select_one('time[datetime]')
                    if time_elem:
                        datetime_attr = time_elem.get('datetime')
                        if datetime_attr:
                            date = self.parse_date(datetime_attr)
                    # Excerpt is in .news-item-description (excluding "Read more")
                    excerpt_elem = item.select_one('.news-item-description')
                    if excerpt_elem:
                        # Get text but remove "Read more" span
                        read_more = excerpt_elem.select_one('.news-item-more')
                        if read_more:
                            read_more.decompose()
                        excerpt = excerpt_elem.get_text(strip=True)
                    if title and url and len(title) >= 10:
                        return self.create_article(title, url, date, excerpt)
        
        # Strategy 0d: Cardinia listing pattern
        # Structure: article.listing > a.listing__link > h2.listing__heading + p.listing__summary
        if item.name == 'article' and 'listing' in item.get('class', []):
            listing_link = item.select_one('a.listing__link')
            if listing_link:
                url = listing_link.get('href', '')
                # Title is in h2.listing__heading
                title_elem = item.select_one('h2.listing__heading, .listing__heading')
                if title_elem:
                    title = self._get_clean_title(title_elem)
                    # Excerpt is in p.listing__summary
                    excerpt_elem = item.select_one('p.listing__summary, .listing__summary')
                    if excerpt_elem:
                        excerpt = excerpt_elem.get_text(strip=True)
                    # Date is in .listing__meta--date
                    date_elem = item.select_one('.listing__meta--date, .listing__meta')
                    if date_elem:
                        date = self.parse_date(date_elem.get_text(strip=True))
                    if title and url and len(title) >= 10:
                        return self.create_article(title, url, date, excerpt)

        # Strategy 0f: Greater Geelong pattern
        # Structure: a.cont-item-news > .cont-item-right > .cont-item-title + .cont-item-desc
        if item.name == 'a' and 'cont-item-news' in item.get('class', []):
            url = item.get('href', '')
            title_elem = item.select_one('.cont-item-title')
            if title_elem:
                title = title_elem.get_text(strip=True)
                excerpt_elem = item.select_one('.cont-item-desc')
                if excerpt_elem:
                    excerpt = excerpt_elem.get_text(strip=True)
                
                # Date is often missing in listing for Geelong, but check tags just in case
                # or try to find a date-like string in the description if it starts with one
                
                if title and url and len(title) >= 10:
                    return self.create_article(title, url, date, excerpt)

        # Strategy 0g: Melbourne City Council pattern
        # Structure: div.card-medium > div.card-medium--content > a > h3.card-medium--content-title
        if item.name == 'div' and 'card-medium' in item.get('class', []):
            content_div = item.select_one('.card-medium--content')
            if content_div:
                link = content_div.find('a')
                if link:
                    url = link.get('href', '')
                    title_elem = link.select_one('.card-medium--content-title')
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        excerpt_elem = link.select_one('.content p')
                        if excerpt_elem:
                            excerpt = excerpt_elem.get_text(strip=True)
                        
                        if title and url and len(title) >= 10:
                            return self.create_article(title, url, date, excerpt)

        # Strategy 0h: Port Phillip pattern
        # Structure: div.i-tile > a.i-tile__link > h2.i-tile__text--title
        if item.name == 'div' and 'i-tile' in item.get('class', []):
            link = item.select_one('a.i-tile__link')
            if link:
                url = link.get('href', '')
                title_elem = link.select_one('.i-tile__text--title')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    
                    # Date is in .i-tile__text--subtitle
                    date_elem = link.select_one('.i-tile__text--subtitle')
                    if date_elem:
                        date = self.parse_date(date_elem.get_text(strip=True))
                    
                    # Excerpt is in the next p tag
                    # Find all p tags and take the one that isn't the subtitle
                    for p in link.select('p'):
                        if 'i-tile__text--subtitle' not in p.get('class', []):
                            excerpt = p.get_text(strip=True)
                            break
                    
                    if title and url and len(title) >= 10:
                        return self.create_article(title, url, date, excerpt)

        # Strategy 0i: Darebin pattern
        # Structure: div.list-item-container > article > a
        if item.name == 'div' and 'list-item-container' in item.get('class', []):
            link = item.select_one('article > a')
            if link:
                url = link.get('href', '')
                title_elem = link.select_one('.list-item-title')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                
                date_elem = link.select_one('.published-on')
                if date_elem:
                    # "Published on 28 November 2025"
                    date_text = date_elem.get_text(strip=True).replace('Published on', '').strip()
                    date = self.parse_date(date_text)
                
                # Excerpt is a <p> tag that is NOT .oc-thumbnail-image, .published-on, or .tagged-as-list
                # In the HTML: <p>The draft...</p> (no class)
                for p in link.select('p'):
                    if not p.get('class'):
                        excerpt = p.get_text(strip=True)
                        break
                
                if title and url and len(title) >= 10:
                    return self.create_article(title, url, date, excerpt)
        
        # Strategy 0j: Yarra pattern
        # Structure: a.card-y
        if item.name == 'a' and 'card-y' in item.get('class', []):
            url = item.get('href', '')
            title_elem = item.select_one('h3')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # Date is in the second div inside the absolute div in the media div
            # <div class="absolute ..."><div ...>News</div><div ...>Date</div></div>
            # We can look for text that parses as date
            date = None
            for div in item.select('div.absolute div'):
                d = self.parse_date(div.get_text(strip=True))
                if d:
                    date = d
                    break
            
            if title and url and len(title) >= 10:
                return self.create_article(title, url, date, None)

        # Strategy 0e: Check if the item itself is a link (whole card is clickable)
        if item.name == 'a' and item.get('href'):
            url = item.get('href', '')
            # Look for title inside
            title_elem = item.select_one('h2, h3, h4, .title')
            if title_elem:
                title = title_elem.get_text(strip=True)
            else:
                # Use aria-label if available
                title = item.get('aria-label', '')
            
            if title and url and len(title) >= 10:
                # Find date
                date_elem = item.select_one(self.DATE_SELECTOR)
                if date_elem:
                    date = self.parse_date(date_elem.get_text(strip=True))
                
                # Find excerpt
                # Try specific selectors first to avoid matching date p tags
                excerpt_elem = item.select_one('.card__description, .preview, .excerpt, .summary, .description')
                if not excerpt_elem:
                    # Fallback to generic p, but ensure it's not the date element
                    for p in item.select('p'):
                        if p != date_elem:
                            excerpt_elem = p
                            break
                
                if excerpt_elem:
                    excerpt = excerpt_elem.get_text(strip=True)
                
                return self.create_article(title, url, date, excerpt)
        
        # Strategy 0.5: Title NOT in link, but separate "Read more" link exists
        # Common in GovCMS sites like Latrobe (.teaser__title + .read-more link)
        title_elem = item.select_one('.teaser__title, h3.teaser__title')
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            # Look for read-more or similar link
            read_more = item.select_one('a.read-more-overlay-visible, a.read-more, a[href*="/news-and-media/"], a[href*="/media-release"]')
            if read_more and title_text and len(title_text) >= 10:
                url = read_more.get('href', '')
                if url:
                    title = title_text
                    # Find date
                    date_elem = item.select_one('.teaser__info, .node-post-date, ' + self.DATE_SELECTOR)
                    if date_elem:
                        date = self.parse_date(date_elem.get_text(strip=True))
                    # Find excerpt
                    excerpt_elem = item.select_one('.teaser__summary, .field--name-body')
                    if excerpt_elem:
                        excerpt = excerpt_elem.get_text(strip=True)
                    return self.create_article(title, url, date, excerpt)
        
        # Strategy 1: Look for specific title class patterns (most reliable)
        # First check for heading elements inside - Cardinia-style (listing__link wraps h2 + p)
        title_elem = item.select_one('h2.listing__heading, h3.listing__heading, .listing__heading')
        if title_elem:
            title = title_elem.get_text(strip=True)
            # URL is on the parent link
            parent_link = title_elem.find_parent('a')
            if parent_link and parent_link.get('href'):
                url = parent_link.get('href', '')
                # Get excerpt from sibling summary element
                excerpt_elem = item.select_one('p.listing__summary, .listing__summary')
                if excerpt_elem:
                    excerpt = excerpt_elem.get_text(strip=True)
                # Get date from listing__meta
                date_elem = item.select_one('.listing__meta--date, .listing__meta')
                if date_elem:
                    date = self.parse_date(date_elem.get_text(strip=True))
                if title and url and len(title) >= 10:
                    return self.create_article(title, url, date, excerpt)
        
        title_elem = item.select_one('a.views-field-title, .title a, a.title, h2 a, h3 a, .field--name-title a, .news-title a')
        
        # Strategy 2: If not found, look for link with longest text (usually the title)
        if not title_elem:
            links = item.find_all('a', href=True)
            best_link = None
            best_length = 0
            for link in links:
                text = link.get_text(strip=True)
                href = link.get('href', '')
                # Skip links that look like dates
                if re.match(r'^(Published|Updated)?\s*\d', text):
                    continue
                # Skip category/tag links
                if '/category/' in href or '/tag/' in href or '?category=' in href:
                    continue
                # Skip pagination
                if '?page=' in href:
                    continue
                # Prefer links with news URL pattern
                if ('/news/' in href or '/news-and-media/' in href) and len(text) > best_length:
                    best_link = link
                    best_length = len(text)
                elif not best_link and len(text) > best_length:
                    best_link = link
                    best_length = len(text)
            title_elem = best_link
        
        if not title_elem:
            return None
        
        title = title_elem.get_text(strip=True)
        url = title_elem.get('href', '')
        
        if not title or not url or len(title) < 10:
            return None
        
        # Find date - look in various places
        # First check for time element (most accurate)
        time_elem = item.select_one('time[datetime]')
        if time_elem:
            datetime_attr = time_elem.get('datetime')
            if datetime_attr:
                date = self.parse_date(datetime_attr)
        
        # Fallback to date selectors
        if not date:
            date_elem = item.select_one(self.DATE_SELECTOR)
            if date_elem:
                date = self.parse_date(date_elem.get_text(strip=True))
        
        # Fallback: Try to parse date from URL
        if not date and url:
            # Look for YYYY/MM/DD or YYYY-MM-DD
            url_date_match = re.search(r'/(\d{4})[/-](\d{1,2})[/-](\d{1,2})', url)
            if url_date_match:
                try:
                    year, month, day = url_date_match.groups()
                    date = datetime(int(year), int(month), int(day))
                except ValueError:
                    pass
        
        # Find excerpt
        excerpt_elem = item.select_one('a.views-field-body, .excerpt, .summary, .description, .field--name-body, .teaser')
        if excerpt_elem and excerpt_elem != title_elem:
            excerpt = excerpt_elem.get_text(strip=True)
        
        # Filter out promotional/category cards (no date) for news-and-media URLs
        # These are often static pages like "GB news and magazine" on Greater Bendigo
        # Actual news articles should have a publication date
        if not date and '/news-and-media/' in url:
            return None
        
        return self.create_article(title, url, date, excerpt)


class InnerWestScraper(CardScraper):
    """
    Scraper for Inner West Council.
    
    Inner West Council does not display dates on the listing page.
    We must fetch each article page to get the date.
    """
    
    def scrape(self) -> List[NewsArticle]:
        # Use the default CardScraper logic to find articles (title, url)
        articles = super().scrape()
        
        # Clean titles
        for article in articles:
            if article.title.startswith("Click through to "):
                article.title = article.title.replace("Click through to ", "").strip()
        
        # Now fetch details for each article to get the date
        # We limit to the first 10 articles to avoid hammering the server
        # and because we only care about recent news anyway
        for article in articles[:10]:
            if not article.date:
                self._fetch_article_details(article)
                # Add a delay to be polite and avoid 429s
                time.sleep(1)
                
        return articles[:10]
    
    def _fetch_article_details(self, article: NewsArticle):
        """Fetch article page to find the date."""
        try:
            html = self.fetch_page(article.url)
            if not html:
                return
                
            soup = self.parse_html(html)
            
            # Date is usually plain text after the h1
            # We search the whole text for a date pattern to be safe
            # Pattern: Dayname? Day Month Year (e.g. Tuesday 11 November 2025)
            
            # Get text from the main content area if possible, to avoid header dates
            content = soup.select_one('#page-content, .content-area, main')
            if content:
                text = content.get_text(" ", strip=True)
            else:
                text = soup.get_text(" ", strip=True)
            
            # Regex for date
            # We look for: Dayname? Day Month Year
            # We handle the "Novemeber" typo specifically
            date_match = re.search(r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', text)
            
            if date_match:
                day, month, year = date_match.groups()
                # Fix known typos
                if month.lower() == 'novemeber':
                    month = 'November'
                
                date_str = f"{day} {month} {year}"
                article.date = self.parse_date(date_str)
                
        except Exception as e:
            print(f"Error fetching details for {article.url}: {e}")


class RSSScraper(BaseScraper):
    """Scraper for RSS feeds."""
    
    def __init__(self, council_id: str, council_name: str, news_url: str, use_curl: bool = False, mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, limit: Optional[int] = None, proxy: Optional[str] = None):
        super().__init__(council_id, council_name, news_url, use_curl, mobile_mode, limit, proxy)
        self.selectors = selectors or {}
    
    def scrape(self) -> List[NewsArticle]:
        content = self.fetch_page(self.news_url)
        if not content:
            return []
            
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
            desc_elem = item.find('description')
            date_elem = item.find('pubDate')
            
            if not title_elem or not link_elem:
                continue
                
            title = title_elem.get_text(strip=True)
            link = link_elem.get_text(strip=True)
            
            date = None
            if date_elem:
                try:
                    date = date_parser.parse(date_elem.get_text(strip=True))
                except Exception:
                    pass
            
            excerpt = None
            if desc_elem:
                desc_text = desc_elem.get_text(strip=True)
                # Remove HTML tags from description
                desc_soup = BeautifulSoup(desc_text, 'html.parser')
                excerpt = desc_soup.get_text(strip=True)[:200] + "..."
            
            articles.append(self.create_article(title, link, date, excerpt))
            
        return articles


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
        
        return scraper_class(
            council_id=council['id'],
            council_name=council['name'],
            news_url=council['news_url'],
            use_curl=use_curl,
            mobile_mode=mobile_mode,
            selectors=selectors,
            limit=limit,
            proxy=use_proxy
        )

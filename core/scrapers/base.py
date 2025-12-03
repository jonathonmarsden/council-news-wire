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
    
    def __init__(self, council_id: str, council_name: str, news_url: str, use_curl: bool = False, mobile_mode: bool = False, limit: Optional[int] = None, proxy: Optional[str] = None, impersonate: str = "chrome110"):
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
            impersonate: Browser to impersonate when using curl (e.g. chrome110, safari15_5)
        """
        self.council_id = council_id
        self.council_name = council_name
        self.news_url = news_url
        self.use_curl = use_curl
        self.mobile_mode = mobile_mode
        self.limit = limit
        self.proxy = proxy
        self.impersonate = impersonate
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
                
                # Use configured impersonation
                impersonate = self.impersonate
                
                response = curl_requests.get(
                    url, 
                    impersonate=impersonate, 
                    proxies=proxies, 
                    timeout=60
                )
                
                if response.status_code == 200:
                    # Check for Incapsula block
                    if "Incapsula" in response.text or "Request unsuccessful" in response.text:
                        print("DEBUG: curl_cffi blocked by Incapsula")
                        return None
                        
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

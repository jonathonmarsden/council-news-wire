"""
Base scraper class for council news pages.

Provides common functionality for scraping news articles from Victorian council websites.
"""

from __future__ import annotations

import re
import subprocess
import time
import html
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from core.utils import get_logger

logger = get_logger(__name__)

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False


@dataclass
class NewsArticle:
    """Represents a news article from a council website."""
    
    council_id: str
    council_name: str
    title: str
    url: str
    date: Optional[datetime] = None
    excerpt: Optional[str] = None
    
    def __post_init__(self):
        """Sanitize fields after initialization."""
        # Ensure URL is ASCII-safe (fix mojibake like smart quotes or em-dashes)
        if self.url:
             # Safe characters include common URL symbols. 
             # We want to encode ONLY non-ascii mostly.
             try:
                 self.url = quote(self.url, safe=":/?#=&%") # % mostly for already encoded things
             except Exception as e:
                 logger.error(f"Failed to sanitize URL '{self.url[:50]}...': {e}")
                 # Fallback: simple ascii strip as last resort? 
                 # Or just leave it and let the DB choke? 
                 # Let's leave it but we've logged it.

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
    
    def __init__(self, council_id: str, council_name: str, news_url: str, use_curl: bool = False, use_cloudscraper: bool = False, mobile_mode: bool = False, limit: Optional[int] = None, proxy: Optional[str] = None, impersonate: str = "chrome110", **kwargs):
        """
        Initialize the scraper.
        
        Args:
            council_id: Unique identifier for the council (kebab-case)
            council_name: Human-readable council name
            news_url: URL of the council's news page
            use_curl: Whether to use curl for WAF bypass
            use_cloudscraper: Whether to use cloudscraper for Cloudflare bypass
            mobile_mode: Whether to impersonate a mobile device (iPhone)
            limit: Maximum number of articles to scrape
            proxy: Proxy URL (e.g. http://user:pass@host:port)
            impersonate: Browser to impersonate when using curl (e.g. chrome110, safari15_5)
            **kwargs: Additional arguments ignored by base class
        """
        self.council_id = council_id
        self.council_name = council_name
        self.news_url = news_url
        self.use_curl = use_curl
        self.use_cloudscraper = use_cloudscraper
        self.mobile_mode = mobile_mode
        self.limit = limit
        self.proxy = proxy
        self.impersonate = impersonate
        self.verify_ssl = kwargs.pop('verify_ssl', True)
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.session.verify = self.verify_ssl
        
        if self.use_cloudscraper and CLOUDSCRAPER_AVAILABLE:
            self.scraper = cloudscraper.create_scraper()
        else:
            self.scraper = None
        
        # Don't set proxies immediately - we'll try direct first in fetch_page
        # unless we decide otherwise later.

    def _retry(self, fn: Callable[[], Optional[str]], max_attempts: int = 3, base_delay: float = 2.0) -> Optional[str]:
        """
        Call fn() up to max_attempts times, with exponential backoff on None/exception.

        Delays: 2s, 4s (base_delay * 2^attempt). Returns the first non-None result,
        or None if all attempts fail.
        """
        for attempt in range(max_attempts):
            try:
                result = fn()
                if result is not None:
                    return result
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{max_attempts} raised {type(e).__name__}: {e}")
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)
                logger.debug(f"Retrying in {delay:.0f}s (attempt {attempt + 1}/{max_attempts})")
                time.sleep(delay)
        return None

    def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch a web page, handling WAF protection if needed.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string, or None if fetch failed
        """
        # If proxy is configured, we MUST use it to protect IP reputation.
        if self.proxy:
            # Configure requests session
            self.session.proxies = {
                'http': self.proxy,
                'https': self.proxy
            }

            if self.use_cloudscraper and CLOUDSCRAPER_AVAILABLE:
                return self._retry(lambda: self._fetch_with_cloudscraper(url))

            if self.use_curl:
                return self._fetch_with_curl(url, use_proxy=True)

            return self._retry(lambda: self._fetch_with_requests(url))

        # No proxy - direct connection
        self.session.proxies = {}

        if self.use_cloudscraper and CLOUDSCRAPER_AVAILABLE:
            return self._retry(lambda: self._fetch_with_cloudscraper(url))

        if self.use_curl:
            return self._fetch_with_curl(url, use_proxy=False)

        return self._retry(lambda: self._fetch_with_requests(url))
    
    def _fetch_with_cloudscraper(self, url: str) -> Optional[str]:
        """Fetch a URL using cloudscraper to bypass Cloudflare."""
        if not CLOUDSCRAPER_AVAILABLE:
            logger.warning("Cloudscraper not available")
            return None
            
        try:
            logger.info(f"Using cloudscraper for {url}")
            # Use self.scraper if available (created in init)
            scraper = self.scraper if self.scraper else cloudscraper.create_scraper()
            
            proxies = None
            if self.proxy:
                 proxies = {'http': self.proxy, 'https': self.proxy}
            
            response = scraper.get(url, proxies=proxies, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Cloudscraper error for {url}: {e}")
            return None

    def _fetch_with_requests(self, url: str) -> Optional[str]:
        """Fetch page using requests library."""
        try:
            # self.session.proxies is already set in fetch_page
            response = self.session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.warning(f"Error fetching {url}: {e}")
            return None
    
    def _fetch_with_curl(self, url: str, use_proxy: bool = False) -> Optional[str]:
        """Fetch page using curl for WAF bypass."""
        logger.debug(f"Fetching with curl (Proxy: {use_proxy}): {url}")
        
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
                    # Check for Incapsula or Cloudflare block
                    r_text = response.text
                    if "Incapsula" in r_text or "Request unsuccessful" in r_text:
                        logger.warning("curl_cffi blocked by Incapsula")
                        return None
                    
                    lower_text = r_text.lower()
                    # Check for specific Cloudflare block indicators, avoiding false positives like cdnjs.cloudflare.com
                    block_indicators = [
                        "<title>just a moment...</title>", 
                        "<title>attention required! | cloudflare</title>",
                        "cf-error-details",
                        "ray id:", # Often in block pages
                        "please wait..."
                    ]
                    
                    # Only flag as blocked if we see strong indicators
                    if ("error code:" in lower_text and "cloudflare" in lower_text) or \
                       any(ind in lower_text for ind in block_indicators):
                         logger.warning(f"curl_cffi blocked by Cloudflare (Content detection)")
                         return None

                    logger.debug(f"curl_cffi success, length: {len(r_text)}")
                    return r_text
                else:
                    logger.warning(f"curl_cffi failed with status {response.status_code}")
            except Exception as e:
                logger.debug(f"curl_cffi exception: {e}")
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
                # Validate output
                lower_stdout = result.stdout.lower()
                if "error code:" in lower_stdout or "cloudflare" in lower_stdout or "access denied" in lower_stdout:
                    logger.warning(f"Curl blocked by Cloudflare/WAF")
                    return None
                    
                logger.debug(f"Curl success, length: {len(result.stdout)}")
                if len(result.stdout) < 1000:
                    logger.debug(f"Short content: {result.stdout[:200]}...")
                return result.stdout
            logger.warning(f"Curl error for {url}: {result.stderr}")
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"Curl timeout for {url}")
            return None
        except Exception as e:
            logger.error(f"Curl exception for {url}: {e}")
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

        # ISO-8601 (e.g. "2026-06-12T08:13:03+00:00" or "2026-06-12") is
        # unambiguous — parsing it with dayfirst=True swaps day/month for days
        # 1-12. Detect a leading YYYY-MM-DD and parse without dayfirst.
        if re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
            try:
                return date_parser.parse(date_str)
            except (ValueError, TypeError):
                pass

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

        # 1. Unescape HTML entities first (handles &lt;p&gt; -> <p>)
        text = html.unescape(text)

        # 2. Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

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

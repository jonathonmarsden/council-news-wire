"""
Card-based scraper implementation.
"""

import re
import time
from datetime import datetime
from typing import List, Optional, Dict

from .base import BaseScraper, NewsArticle
from core.utils import get_logger

logger = get_logger(__name__)

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
    ARTICLE_SELECTOR = 'article.news-item, article.listing, .news-card, .listing-item, .views-row, .content-card, .article-container, .media-item, a.card--news, a.card__news-listing, a.card[href*="/news/"], div.card, .article-item, a.cont-item-news, .card-medium, .i-tile, .list-item-container, a.card-y, div.result-container, div.news-listing__item'
    TITLE_SELECTOR = 'h2 a, h3 a, .title a, a.title, .field--name-title a, .news-title a, a[href*="/news/"]'
    DATE_SELECTOR = '.date, .published, time, .meta-date, .field--name-created, .news-date, .card__meta'
    EXCERPT_SELECTOR = '.card__description, .excerpt, .summary, .description, .field--name-body, .teaser, p'
    
    def __init__(self, council_id: str, council_name: str, news_url: str, use_curl: bool = False, use_cloudscraper: bool = False, mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, limit: Optional[int] = None, proxy: Optional[str] = None, impersonate: str = "chrome124", **kwargs):
        super().__init__(council_id, council_name, news_url, use_curl, use_cloudscraper, mobile_mode, limit, proxy, impersonate, **kwargs)
        self.selectors = selectors or {}

    def _get_clean_title(self, element) -> str:
        """Extract title text from an element, excluding date/metadata elements."""
        if not element:
            return ""
            
        # Debug
        # print(f"Cleaning title from: {str(element)[:100]}")
            
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
                # Note: Be careful with 'label' as it catches 'field--label-hidden' which often contains the title in Drupal
                if any(c in classes_str for c in ['date', 'published', 'time', 'meta', 'right', 'summary', 'excerpt', 'description', 'teaser', 'body']):
                    continue
                if 'label' in classes_str and 'hidden' not in classes_str:
                     continue
                
                if child.name == 'time':
                    continue
                # Skip paragraph tags inside title containers (usually summaries)
                if child.name == 'p':
                    continue
                    
                # Recursively get text from child
                text = child.get_text(" ", strip=True)
                # print(f"  Child {child.name} text: '{text}'")
                text_parts.append(text)
            elif child.string:
                text = child.string.strip()
                # print(f"  String child text: '{text}'")
                text_parts.append(text)
                
        text = " ".join(filter(None, text_parts))
        
        # Remove common prefixes
        text = re.sub(r'^(Media Release|Press Release|News Release)[:\s-]*', '', text, flags=re.IGNORECASE)
        
        return text.strip()

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

        html = self.fetch_page_or_raise(self.news_url)
        
        soup = self.parse_html(html)
        
        # First try structured article elements
        # Use configured selector if available, otherwise use default list
        article_selector = self.selectors.get('item_selector') or self.ARTICLE_SELECTOR
        
        items = soup.select(article_selector)
        print(f"Found {len(items)} items with selector {article_selector}")
        
        for item in items:
            if self.limit and len(articles) >= self.limit:
                break
            article = self._parse_article(item)
            if article:
                articles.append(article)
            else:
                print("Failed to parse article from item")
        
        # If no articles found AND no selectors were configured, try finding
        # news links directly. For councils WITH a configured selector, a miss
        # means the markup changed — return [] so the empty-run breaker and
        # silent-failure alert fire, instead of sweeping every <a> on the page
        # and posting nav links as "articles".
        if not articles and not self.selectors.get('item_selector'):
            articles = self._scrape_links_directly(soup)
            if self.limit:
                articles = articles[:self.limit]
            
        # Check if we need to fetch details (for date, full content, or full title)
        should_fetch_details = False
        if self.selectors.get('date_selector'):
            should_fetch_details = True
        if self.selectors.get('full_content_selector'):
            should_fetch_details = True
        if self.selectors.get('full_title_selector'):
            should_fetch_details = True
            
        if should_fetch_details:
            print(f"Fetching details for up to 10 articles (Selectors: date={bool(self.selectors.get('date_selector'))}, content={bool(self.selectors.get('full_content_selector'))}, title={bool(self.selectors.get('full_title_selector'))})")
            # Limit to first 10 to avoid excessive requests
            for article in articles[:10]:
                # Fetch if missing date OR if we want full content OR full title
                condition_date = (not article.date and self.selectors.get('date_selector'))
                condition_content = bool(self.selectors.get('full_content_selector'))
                condition_title = bool(self.selectors.get('full_title_selector'))
                
                if condition_date or condition_content or condition_title:
                    print(f"Fetching details for: {article.url}")
                    self._fetch_article_details(article)
                    # Be polite
                    time.sleep(0.2)
        
        return articles
    
    def _fetch_article_details(self, article: NewsArticle):
        """Fetch article page to find the date and optionally full content."""
        try:
            html = self.fetch_page(article.url)
            if not html:
                return
                
            soup = self.parse_html(html)
            
            # Try configured date_selector
            date_selector = self.selectors.get('date_selector')
            if date_selector and not article.date:
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

            # Try configured full_title_selector
            title_selector = self.selectors.get('full_title_selector')
            if title_selector:
                title_elem = soup.select_one(title_selector)
                if title_elem:
                    text = self._get_clean_title(title_elem)
                    print(f"  Found full title: '{text}' (Old: '{article.title}')")
                    if text and (len(text) > len(article.title) or article.title.endswith('...')):
                        # Only update if the new title is longer (assuming the list one was truncated)
                        # or if the list one was very short/ellipsis OR ends with ...
                        article.title = text
                else:
                    print(f"  Full title selector '{title_selector}' found nothing.")

            # Try configured full_content_selector
            content_selector = self.selectors.get('full_content_selector')
            if content_selector:
                content_elem = soup.select_one(content_selector)
                if content_elem:
                    # Use clean_text to strip tags and normalize
                    text = self.clean_text(str(content_elem))
                    if text:
                        print(f"  Found full content (len={len(text)})")
                        article.excerpt = text
                else:
                    print(f"  Full content selector '{content_selector}' found nothing.")

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
                if text.endswith(date_str):
                    text = text[:-len(date_str)].strip()
                elif text.endswith(date_str.replace(" ", "")):
                     text = text[:-len(date_str.replace(" ", ""))].strip()
            
            # 2. Check parent/siblings if not found
            if not date:
                parent = link.find_parent()
                if parent:
                    # Look for date text in parent or siblings
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
        # debug-level: at print level this emitted up to 1KB of HTML per card
        # per council per run — megabytes of interleaved cron-log noise
        logger.debug(f"Parsing item: {item.prettify()[:1000]}...")
        title = None
        url = None
        date = None
        excerpt = None
        
        # Strategy -1: Configured selectors
        if self.selectors:
            # Link
            link_selector = self.selectors.get('link_selector')
            # print(f"DEBUG: link_selector={link_selector} for {self.council_id}")
            if link_selector:
                if link_selector == 'self' or link_selector == 'this':
                    if item.name == 'a':
                        link_elem = item
                    elif item.has_attr('id'):
                        # Special handling for tab/anchor targets
                        # Construct URL from base news URL + ID
                        base_url = self.news_url.split('#')[0]
                        url = f"{base_url}#{item['id']}"
                        link_elem = None # URL already set
                    else:
                        link_elem = None
                else:
                    link_elem = item.select_one(link_selector)
                
                if link_elem:
                    url = link_elem.get('href', '')
                else:
                    # Debug
                    # print(f"Could not find link with selector {link_selector} in {str(item)[:50]}...")
                    pass
            
            # Title
            title_selector = self.selectors.get('title_selector')
            if title_selector:
                if title_selector == 'self' or title_selector == 'this':
                    title_elem = item
                else:
                    title_elem = item.select_one(title_selector)
                    
                if title_elem:
                    logger.debug(f"Found title elem: {str(title_elem)[:100]}")
                    title = self._get_clean_title(title_elem)
                    logger.debug(f"Extracted title: '{title}'")
                else:
                    # Debug
                    # print(f"Could not find title with selector {title_selector} in {str(item)[:50]}...")
                    pass
            
            # Date
            date_selector = self.selectors.get('date_selector')
            if date_selector:
                date_elem = item.select_one(date_selector)
                if date_elem:
                    date_text = date_elem.get_text(" ", strip=True)
                    date = self.parse_date(date_text)
            
            # Excerpt (optional)
            excerpt_selector = self.selectors.get('content_selector') or self.selectors.get('excerpt_selector')
            if excerpt_selector:
                excerpt_elem = item.select_one(excerpt_selector)
                if excerpt_elem:
                    raw_excerpt = excerpt_elem.get_text(" ", strip=True)
                    excerpt = self._clean_excerpt(raw_excerpt, title)
            
            if title and url:
                # Fallback: Try to extract date from URL if not found
                if not date:
                    # Match /YYYY/MM/DD/ pattern
                    date_match = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
                    if date_match:
                        try:
                            year, month, day = map(int, date_match.groups())
                            date = datetime(year, month, day)
                        except ValueError:
                            pass
                
                return self.create_article(title, url, date, excerpt)
            else:
                print(f"Missing title or url. Title: '{title}', URL: '{url}'")

        # Strategy 0: Card div with link inside containing .card__title (Golden Plains/GovCMS pattern)
        if item.name == 'div' and 'card' in item.get('class', []):
            card_link = item.select_one('a[href*="/news/"], a[href*="/news-and-media/"]')
            if card_link:
                url = card_link.get('href', '')
                title_elem = item.select_one('.card__title h2, .card__title h3, .card__title')
                if title_elem:
                    title = self._get_clean_title(title_elem)
                    date_elem = item.select_one('.card__date time, .card__date, time[datetime]')
                    if date_elem:
                        datetime_attr = date_elem.get('datetime')
                        if datetime_attr:
                            date = self.parse_date(datetime_attr)
                        else:
                            date = self.parse_date(date_elem.get_text(strip=True))
                        excerpt_elem = item.select_one('.card__excerpt, .card__summary, .card__description, .card__desc')
                        if excerpt_elem:
                            excerpt = excerpt_elem.get_text(strip=True)
                        if title and url and len(title) >= 10:
                            return self.create_article(title, url, date, excerpt)
        
        # Strategy 0a: Webflow article-item pattern (East Gippsland, etc)
        if item.name == 'div' and 'article-item' in item.get('class', []):
            article_link = item.select_one('a.article-link')
            if article_link:
                url = article_link.get('href', '')
                title_elem = item.select_one('h4, h3, h2')
                if title_elem:
                    title = self._get_clean_title(title_elem)
                    date_elem = item.select_one('.small-text.teal, .small-text.caps, .article-date')
                    if date_elem:
                        date = self.parse_date(date_elem.get_text(strip=True))
                    excerpt_elem = item.select_one('.article-body-wrap .small-text, .article-body-wrap, .article-excerpt')
                    if excerpt_elem:
                        excerpt = excerpt_elem.get_text(strip=True)
                    if title and url and len(title) >= 10:
                        return self.create_article(title, url, date, excerpt)
        
        # Strategy 0b: Webflow media-item pattern (Wellington, etc)
        if item.name == 'div' and 'media-item' in item.get('class', []):
            media_link = item.select_one('a.media-link')
            if media_link:
                url = media_link.get('href', '')
                title_elem = item.select_one('.media-title')
                if title_elem:
                    title = self._get_clean_title(title_elem)
                    date_elem = item.select_one('.media-date')
                    if date_elem:
                        date = self.parse_date(date_elem.get_text(strip=True))
                    if title and url and len(title) >= 10:
                        return self.create_article(title, url, date, excerpt)
        
        # Strategy 0c: Greater Shepparton news-item pattern
        if item.name == 'article' and 'news-item' in item.get('class', []):
            news_link = item.select_one('a.news-item-link')
            if news_link:
                url = news_link.get('href', '')
                title_elem = item.select_one('h1.news-item-heading, .news-item-heading')
                if title_elem:
                    title = self._get_clean_title(title_elem)
                    time_elem = item.select_one('time[datetime]')
                    if time_elem:
                        datetime_attr = time_elem.get('datetime')
                        if datetime_attr:
                            date = self.parse_date(datetime_attr)
                    excerpt_elem = item.select_one('.news-item-description')
                    if excerpt_elem:
                        read_more = excerpt_elem.select_one('.news-item-more')
                        if read_more:
                            read_more.decompose()
                        excerpt = excerpt_elem.get_text(strip=True)
                    if title and url and len(title) >= 10:
                        return self.create_article(title, url, date, excerpt)
        
        # Strategy 0d: Cardinia listing pattern
        if item.name == 'article' and 'listing' in item.get('class', []):
            listing_link = item.select_one('a.listing__link')
            if listing_link:
                url = listing_link.get('href', '')
                title_elem = item.select_one('h2.listing__heading, .listing__heading')
                if title_elem:
                    title = self._get_clean_title(title_elem)
                    excerpt_elem = item.select_one('p.listing__summary, .listing__summary')
                    if excerpt_elem:
                        excerpt = excerpt_elem.get_text(strip=True)
                    date_elem = item.select_one('.listing__meta--date, .listing__meta')
                    if date_elem:
                        date = self.parse_date(date_elem.get_text(strip=True))
                    if title and url and len(title) >= 10:
                        return self.create_article(title, url, date, excerpt)

        # Strategy 0f: Greater Geelong pattern
        if item.name == 'a' and 'cont-item-news' in item.get('class', []):
            url = item.get('href', '')
            title_elem = item.select_one('.cont-item-title')
            if title_elem:
                title = title_elem.get_text(strip=True)
                excerpt_elem = item.select_one('.cont-item-desc')
                if excerpt_elem:
                    excerpt = excerpt_elem.get_text(strip=True)
                if title and url and len(title) >= 10:
                    return self.create_article(title, url, date, excerpt)

        # Strategy 0g: Melbourne City Council pattern
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
        if item.name == 'div' and 'i-tile' in item.get('class', []):
            link = item.select_one('a.i-tile__link')
            if link:
                url = link.get('href', '')
                title_elem = link.select_one('.i-tile__text--title')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    date_elem = link.select_one('.i-tile__text--subtitle')
                    if date_elem:
                        date = self.parse_date(date_elem.get_text(strip=True))
                    for p in link.select('p'):
                        if 'i-tile__text--subtitle' not in p.get('class', []):
                            excerpt = p.get_text(strip=True)
                            break
                    if title and url and len(title) >= 10:
                        return self.create_article(title, url, date, excerpt)

        # Strategy 0i: Darebin pattern
        if item.name == 'div' and 'list-item-container' in item.get('class', []):
            link = item.select_one('article > a')
            if link:
                url = link.get('href', '')
                title_elem = link.select_one('.list-item-title')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                date_elem = link.select_one('.published-on')
                if date_elem:
                    date_text = date_elem.get_text(strip=True).replace('Published on', '').strip()
                    date = self.parse_date(date_text)
                for p in link.select('p'):
                    if not p.get('class'):
                        excerpt = p.get_text(strip=True)
                        break
                if title and url and len(title) >= 10:
                    return self.create_article(title, url, date, excerpt)
        
        # Strategy 0j: Yarra pattern
        if item.name == 'a' and 'card-y' in item.get('class', []):
            url = item.get('href', '')
            title_elem = item.select_one('h3')
            if title_elem:
                title = title_elem.get_text(strip=True)
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
            title_elem = item.select_one('h2, h3, h4, .title')
            if title_elem:
                title = title_elem.get_text(strip=True)
            else:
                title = item.get('aria-label', '')
            
            if title and url and len(title) >= 10:
                date_elem = item.select_one(self.DATE_SELECTOR)
                if date_elem:
                    date = self.parse_date(date_elem.get_text(strip=True))
                excerpt_elem = item.select_one('.card__description, .preview, .excerpt, .summary, .description')
                if not excerpt_elem:
                    for p in item.select('p'):
                        if p != date_elem:
                            excerpt_elem = p
                            break
                if excerpt_elem:
                    excerpt = excerpt_elem.get_text(strip=True)
                return self.create_article(title, url, date, excerpt)
        
        # Strategy 0.5: Title NOT in link, but separate "Read more" link exists
        title_elem = item.select_one('.teaser__title, h3.teaser__title')
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            read_more = item.select_one('a.read-more-overlay-visible, a.read-more, a[href*="/news-and-media/"], a[href*="/media-release"]')
            if read_more and title_text and len(title_text) >= 10:
                url = read_more.get('href', '')
                if url:
                    title = title_text
                    date_elem = item.select_one('.teaser__info, .node-post-date, ' + self.DATE_SELECTOR)
                    if date_elem:
                        date = self.parse_date(date_elem.get_text(strip=True))
                    excerpt_elem = item.select_one('.teaser__summary, .field--name-body')
                    if excerpt_elem:
                        excerpt = excerpt_elem.get_text(strip=True)
                    return self.create_article(title, url, date, excerpt)
        
        # Strategy 1: Look for specific title class patterns (most reliable)
        title_elem = item.select_one('h2.listing__heading, h3.listing__heading, .listing__heading')
        if title_elem:
            title = title_elem.get_text(strip=True)
            parent_link = title_elem.find_parent('a')
            if parent_link and parent_link.get('href'):
                url = parent_link.get('href', '')
                excerpt_elem = item.select_one('p.listing__summary, .listing__summary')
                if excerpt_elem:
                    excerpt = excerpt_elem.get_text(strip=True)
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
                if re.match(r'^(Published|Updated)?\s*\d', text):
                    continue
                if '/category/' in href or '/tag/' in href or '?category=' in href:
                    continue
                if '?page=' in href:
                    continue
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
        time_elem = item.select_one('time[datetime]')
        if time_elem:
            datetime_attr = time_elem.get('datetime')
            if datetime_attr:
                date = self.parse_date(datetime_attr)
        
        if not date:
            date_elem = item.select_one(self.DATE_SELECTOR)
            if date_elem:
                date = self.parse_date(date_elem.get_text(strip=True))
        
        if not date and url:
            url_date_match = re.search(r'/(\d{4})[/-](\d{1,2})[/-](\d{1,2})', url)
            if url_date_match:
                try:
                    year, month, day = url_date_match.groups()
                    date = datetime(int(year), int(month), int(day))
                except ValueError:
                    pass
        
        excerpt_elem = item.select_one('a.views-field-body, .excerpt, .summary, .description, .field--name-body, .teaser')
        if excerpt_elem and excerpt_elem != title_elem:
            excerpt = excerpt_elem.get_text(strip=True)
        
        if not date and '/news-and-media/' in url:
            return None
        
        return self.create_article(title, url, date, excerpt)

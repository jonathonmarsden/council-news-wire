"""
Custom scraper implementations for specific councils.
"""

import re
import time
from typing import List, Optional, Dict
from datetime import datetime
from dateutil import parser as date_parser
from urllib.parse import urlparse, parse_qs

from .base import NewsArticle, BaseScraper
from .card import CardScraper

class WordPressScraper(BaseScraper):
    """
    Generic scraper for WordPress sites using the WP API.
    """
    def __init__(self, council_id: str, council_name: str, news_url: str, selectors: dict = None, **kwargs):
        super().__init__(council_id, council_name, news_url, **kwargs)
        self.selectors = selectors or {}
        # Allow api_url to be passed in selectors, or derive from news_url
        self.api_url = self.selectors.get('api_url')
        if not self.api_url:
             # Try to guess: base_url + /wp-json/wp/v2/posts
             from urllib.parse import urlparse
             parsed = urlparse(news_url)
             self.api_url = f"{parsed.scheme}://{parsed.netloc}/wp-json/wp/v2/posts"

    def scrape(self) -> List[NewsArticle]:
        # Use the WordPress API directly as it exposes all data including dates
        # Default params: per_page=20
        api_url = self.api_url
        if '?' not in api_url:
            api_url += "?per_page=20"
        else:
            api_url += "&per_page=20"

        articles = []
        
        try:
            # Fetch API
            response = self.session.get(api_url, timeout=20, verify=False)
            if response.status_code != 200:
                print(f"WordPress API failed for {self.council_name}: {response.status_code}")
                return []
                
            posts = response.json()
            
            for post in posts:
                title = post.get('title', {}).get('rendered')
                # Use 'link' if available, otherwise construct from slug (fallback)
                url = post.get('link')
                if not url and post.get('slug'):
                     # Fallback, might not work for all sites
                     from urllib.parse import urlparse
                     parsed = urlparse(self.news_url)
                     url = f"{parsed.scheme}://{parsed.netloc}/{post.get('slug')}"

                date_str = post.get('date')
                
                if not title or not url:
                    continue
                    
                # Parse date
                date_obj = None
                if date_str:
                    try:
                        date_obj = date_parser.parse(date_str)
                    except:
                        pass
                
                # Clean title
                if title:
                    from bs4 import BeautifulSoup
                    title = BeautifulSoup(title, "html.parser").get_text()

                # Get content - prefer full content, fall back to excerpt
                content = post.get('content', {}).get('rendered', '')
                if not content:
                    content = post.get('excerpt', {}).get('rendered', '')

                article = self.create_article(
                    title=title,
                    url=url,
                    date=date_obj,
                    excerpt=content
                )
                articles.append(article)
                
        except Exception as e:
            print(f"Error scraping WordPress for {self.council_name}: {e}")
            
        return articles

class BunburyScraper(WordPressScraper):
    """
    Scraper for City of Bunbury (Next.js / API).
    Kept for backward compatibility, but now inherits from WordPressScraper.
    """
    def __init__(self, council_id: str, council_name: str, news_url: str, selectors: dict = None, **kwargs):
        # Bunbury has a specific CDN URL for the API
        selectors = selectors or {}
        selectors['api_url'] = "https://cdn.bunbury.wa.gov.au/wp-json/wp/v2/posts"
        super().__init__(council_id, council_name, news_url, selectors, **kwargs)

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

class OpenCitiesScraper(BaseScraper):
    """
    Scraper for OpenCities based websites.
    Handles standard OpenCities layouts and Funnelback/Squiz variations.
    """
    def __init__(self, council_id: str, council_name: str, news_url: str, selectors: Dict = None, **kwargs):
        super().__init__(council_id, council_name, news_url, **kwargs)
        self.selectors = selectors or {}

    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page(self.news_url)
        if not html:
            return []
        soup = self.parse_html(html)

        articles = []
        
        # Strategy 1: Standard OpenCities (e.g. Goulburn)
        # Container: .list-container.news-list-container .list-item-container
        items = soup.select('.list-container.news-list-container .list-item-container')
        
        # Strategy 1b: Relaxed OpenCities (e.g. Lake Macquarie - missing .news-list-container)
        if not items:
            items = soup.select('.list-container .list-item-container')
        
        if not items:
            # Strategy 2: Squiz/Funnelback (e.g. Albury)
            # Container: .card
            items = soup.select('.card')
            
        # Strategy 3: JSON embedded in #SearchResult script (e.g. Canning, Stirling, Swan)
        if not items:
            json_script = soup.select_one('#SearchResult')
            if json_script and json_script.string:
                import json
                try:
                    data = json.loads(json_script.string)
                    items_list = data.get('items', [])
                    for item_data in items_list:
                        title = item_data.get('name')
                        url = item_data.get('url')
                        date_str = item_data.get('releaseDate')
                        excerpt = item_data.get('image', {}).get('imageAlt')
                        
                        if not title or not url:
                            continue
                            
                        # Resolve relative URLs
                        if not url.startswith('http'):
                            from urllib.parse import urljoin
                            url = urljoin(self.news_url, url)
                            
                        date_obj = None
                        if date_str:
                            try:
                                date_obj = date_parser.parse(date_str)
                            except:
                                pass
                                
                        article = self.create_article(
                            title=title,
                            url=url,
                            date=date_obj,
                            excerpt=excerpt
                        )
                        articles.append(article)
                    return articles
                except Exception as e:
                    print(f"Error parsing #SearchResult JSON: {e}")
            
        for item in items:
            try:
                # Title
                title_elem = item.select_one('h2.list-item-title, h5')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                
                # Link
                link_elem = item.select_one('article > a, a')
                if not link_elem:
                    continue
                link = link_elem.get('href')
                
                # Handle Funnelback redirects
                if link and 'funnelback' in link and 'url=' in link:
                    from urllib.parse import parse_qs, urlparse
                    parsed = urlparse(link)
                    qs = parse_qs(parsed.query)
                    if 'url' in qs:
                        link = qs['url'][0]
                
                # Resolve relative URLs
                if link and not link.startswith('http'):
                    from urllib.parse import urljoin
                    link = urljoin(self.news_url, link)
                
                # Date
                date_elem = item.select_one('.published-on, .date_updated')
                date_obj = None
                if date_elem:
                    date_text = date_elem.get_text(strip=True).replace('Published on', '').strip()
                    try:
                        date_obj = date_parser.parse(date_text)
                    except:
                        pass
                
                article = self.create_article(
                    title=title,
                    url=link,
                    date=date_obj
                )
                articles.append(article)
            except Exception as e:
                print(f"Error parsing item in OpenCitiesScraper: {e}")
                continue
                
        return articles

class APYScraper(BaseScraper):
    """
    Scraper for Anangu Pitjantjatjara Yankunytjatjara (APY) media releases.
    
    APY publishes news as PDF files with dates encoded in the filename.
    Format examples:
        - APY-GMAppoint-Media-041225-F1.pdf (04 December 2025)
        - APY-Kulilaya-Media-250324-F1.pdf (25 March 2024)
        - APY_New_Board_Members.pdf (no date, use folder year)
    """
    
    def __init__(self, council_id: str, council_name: str, news_url: str, selectors: Dict = None, **kwargs):
        super().__init__(council_id, council_name, news_url, **kwargs)
        self.selectors = selectors or {}
    
    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page(self.news_url)
        if not html:
            return []
            
        soup = self.parse_html(html)
        articles = []
        
        # Find all PDF links
        pdf_links = soup.find_all('a', href=lambda x: x and 'PDF' in x.upper() if x else False)
        
        for link in pdf_links:
            try:
                href = link.get('href', '')
                title = link.get_text(strip=True) or link.get('title', '')
                
                if not title or not href:
                    continue
                    
                # Make URL absolute
                if href.startswith('/'):
                    from urllib.parse import urljoin
                    href = urljoin(self.news_url, href)
                    
                # Try to extract date from filename
                date_obj = self._extract_date_from_filename(href)
                
                article = self.create_article(
                    title=title,
                    url=href,
                    date=date_obj
                )
                articles.append(article)
                
            except Exception as e:
                print(f"Error parsing APY link: {e}")
                continue
                
        return articles
    
    def _extract_date_from_filename(self, url: str) -> Optional[datetime]:
        """Extract date from APY PDF filename patterns."""
        import os
        from urllib.parse import urlparse
        
        path = urlparse(url).path
        filename = os.path.basename(path)
        
        # Pattern 1: DDMMYY format (e.g., 041225 = 04 Dec 2025)
        match = re.search(r'-(\d{2})(\d{2})(\d{2})-', filename)
        if match:
            day, month, year = match.groups()
            try:
                year_full = 2000 + int(year)
                return datetime(year_full, int(month), int(day))
            except ValueError:
                pass
        
        # Pattern 2: Year from folder path (e.g., /2024/ or /2025/)
        year_match = re.search(r'/(\d{4})/', url)
        if year_match:
            year = int(year_match.group(1))
            # Return January 1 of that year as a fallback date
            return datetime(year, 1, 1)
            
        return None


class AspNetScraper(CardScraper):
    """
    Scraper for ASP.NET (Kentico/Spark CMS) sites (e.g. Busselton, Cockburn).
    Follows section links and extracts articles from nested tables/divs.
    """
    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page(self.news_url)
        if not html:
            return []
        soup = self.parse_html(html)

        # Find section links (e.g., /News-From-The-City, /Newsletter, /Media-Releases-and-Responses)
        section_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if (
                ('news' in href.lower() or 'media' in href.lower() or 'newsletter' in href.lower())
                and href.startswith('/')
                and len(href) > 10
            ):
                section_links.append(self.make_absolute_url(href))

        articles = []
        # Visit each section and extract articles using CardScraper logic
        for section_url in section_links[:3]:  # Limit to first 3 sections for speed
            try:
                section_html = self.fetch_page(section_url)
                if not section_html:
                    continue
                section_soup = self.parse_html(section_html)
                # Use CardScraper logic on section_soup
                items = section_soup.select(self.ARTICLE_SELECTOR)
                for item in items:
                    title_elem = item.select_one(self.TITLE_SELECTOR)
                    if not title_elem:
                        continue
                    title = self._get_clean_title(title_elem)
                    link_elem = item.select_one('a[href]')
                    link = link_elem['href'] if link_elem else section_url
                    if link and not link.startswith('http'):
                        link = self.make_absolute_url(link)
                    date_elem = item.select_one(self.DATE_SELECTOR)
                    date_obj = None
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        try:
                            date_obj = date_parser.parse(date_text)
                        except:
                            pass
                    excerpt_elem = item.select_one(self.EXCERPT_SELECTOR)
                    excerpt = excerpt_elem.get_text(strip=True) if excerpt_elem else None
                    article = self.create_article(title, link, date_obj, excerpt)
                    articles.append(article)
            except Exception as e:
                print(f"Error scraping section {section_url}: {e}")
                continue
        return articles


class LGASAScraper(BaseScraper):
    """
    Scraper for SA councils using the LGA SA Funnelback/Squiz search platform.

    These councils share a common CMS (lgasa-web.squiz.cloud) with Cloudflare
    protection. Articles are listed as li.news-listing__item elements. The href
    is a Funnelback redirect URL — we resolve it to the canonical council URL
    by following the redirect (curl_cffi handles the Cloudflare challenge).

    Applies to ~40 SA councils that migrated to this platform around Jan 2026.
    """

    ITEM_SELECTOR = 'li.news-listing__item'
    TITLE_SELECTOR = 'h2.news-listing__item-title'
    DATE_SELECTOR = '.news-listing__item-date'
    EXCERPT_SELECTOR = '.news-listing__item-teaser'
    LINK_SELECTOR = 'a.news-listing__item-link'

    def __init__(self, council_id: str, council_name: str, news_url: str, **kwargs):
        # Always use curl_cffi — these sites are behind Cloudflare
        kwargs['use_curl'] = True
        super().__init__(council_id, council_name, news_url, **kwargs)

    def _resolve_canonical_url(self, redirect_href: str) -> str:
        """
        Extract the canonical article URL from a Funnelback redirect href.
        The redirect URL contains an index_url param pointing to lgasa-web.squiz.cloud.
        Following the full redirect chain resolves to the council's own domain URL.
        We follow the redirect using curl_cffi so Cloudflare is handled.
        """
        try:
            from curl_cffi.requests import Session
            impersonate = getattr(self, 'impersonate', 'chrome124') or 'chrome124'
            with Session(impersonate=impersonate) as session:
                r = session.get(redirect_href, timeout=15, allow_redirects=True)
                if r.url and r.url != redirect_href:
                    return r.url
        except Exception:
            pass
        # Fallback: extract index_url param (Squiz asset URL — not ideal but usable as dedup key)
        qs = parse_qs(urlparse(redirect_href).query)
        index_url = qs.get('index_url', [''])[0]
        return index_url or redirect_href

    def scrape(self) -> List[NewsArticle]:
        content = self.fetch_page(self.news_url)
        if not content:
            return []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        items = soup.select(self.ITEM_SELECTOR)
        articles = []

        for item in items:
            title_el = item.select_one(self.TITLE_SELECTOR)
            date_el = item.select_one(self.DATE_SELECTOR)
            excerpt_el = item.select_one(self.EXCERPT_SELECTOR)
            link_el = item.select_one(self.LINK_SELECTOR)

            if not title_el or not link_el:
                continue

            title = title_el.get_text(strip=True)
            redirect_href = link_el.get('href', '')
            if not redirect_href:
                continue

            url = self._resolve_canonical_url(redirect_href)
            if not url or not url.startswith('http'):
                continue

            date_obj = None
            if date_el:
                try:
                    date_obj = date_parser.parse(date_el.get_text(strip=True), dayfirst=True)
                except Exception:
                    pass

            excerpt = excerpt_el.get_text(strip=True)[:280] if excerpt_el else None

            articles.append(self.create_article(title, url, date_obj, excerpt))

        return articles


class NarromineScraper(BaseScraper):
    """
    Scraper for Narromine Shire Council media releases.

    Narromine lists media releases in a plain HTML table where each row is a
    single ``a.literature`` anchor. The anchor text concatenates a leading
    file icon, the title, and a trailing date span:

        <a class="literature" href="/council/media-releases/...">
            <i class="fa fa-file-text-o"></i>
            What Do You Think? Council Seeks Your Feedback
            <span class="radius right label">01 June 2026</span>
        </a>

    Generic CardScraper selectors can't separate the glued title and date, so
    the default scraper produced garbage dates (e.g. year 7551). Here we read
    the date from the trailing span and take the title as the anchor text with
    that span removed.
    """

    ITEM_SELECTOR = 'div.page-content a.literature'
    DATE_SELECTOR = 'span.label'

    def __init__(self, council_id: str, council_name: str, news_url: str, **kwargs):
        super().__init__(council_id, council_name, news_url, **kwargs)

    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page(self.news_url)
        if not html:
            return []

        soup = self.parse_html(html)
        articles = []

        # The table is ordered newest-first, so honouring self.limit keeps the
        # most recent releases without fetching the full multi-year archive.
        for link in soup.select(self.ITEM_SELECTOR):
            if self.limit and len(articles) >= self.limit:
                break

            href = link.get('href')
            if not href or '/media-releases/' not in href:
                continue

            # Pull the date out of the trailing label span, then remove it so
            # the remaining anchor text is the clean title.
            date_obj = None
            date_el = link.select_one(self.DATE_SELECTOR)
            if date_el:
                date_obj = self.parse_date(date_el.get_text(strip=True))
                date_el.extract()

            title = link.get_text(strip=True)
            if not title:
                continue

            articles.append(self.create_article(title, href, date_obj))

        return articles


class CatalystBrowserScraper(BaseScraper):
    """
    Scraper for the newer JS-rendered variant of the Catalyst CMS used by
    several larger WA councils (Melville, Rockingham, Kwinana, Murray,
    Laverton).

    Unlike the classic CatalystScraper (static ``.module-list .row``), these
    sites load their news list client-side into ``.pageTypeListing-results``
    via an AJAX search call, so the static HTML is empty. We render the page
    with Playwright, then read each result anchor. The anchor text is
    "DD Month YYYY Title" (date glued to the title), which we split with a
    leading-date regex.
    """

    RESULTS_SELECTOR = '.pageTypeListing-results'
    DATE_RE = re.compile(r'^(\d{1,2}\s+[A-Za-z]+\s+20\d\d)\s+(.+)$', re.S)

    def __init__(self, council_id: str, council_name: str, news_url: str, **kwargs):
        super().__init__(council_id, council_name, news_url, **kwargs)

    def scrape(self) -> List[NewsArticle]:
        from playwright.sync_api import sync_playwright

        ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
        html = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_context(user_agent=ua).new_page()
                page.goto(self.news_url, timeout=60000, wait_until='networkidle')
                # Wait for the AJAX-populated results to appear.
                try:
                    page.wait_for_selector(f'{self.RESULTS_SELECTOR} a[href]', timeout=15000)
                except Exception:
                    pass
                time.sleep(2)
                html = page.content()
                browser.close()
        except Exception as e:
            print(f"Catalyst browser scrape failed for {self.council_name}: {e}")
            return []

        if not html:
            return []

        soup = self.parse_html(html)
        results = soup.select_one(self.RESULTS_SELECTOR)
        if not results:
            return []

        articles = []
        seen = set()
        for a in results.select('a[href]'):
            href = a.get('href', '')
            if '/news' not in href.lower() and '/latest-news' not in href.lower():
                continue
            text = a.get_text(' ', strip=True)
            m = self.DATE_RE.match(text)
            if not m:
                continue
            date_obj = self.parse_date(m.group(1))
            title = m.group(2).strip()
            url = self.make_absolute_url(href)
            if not title or url in seen:
                continue
            seen.add(url)
            articles.append(self.create_article(title, url, date_obj))

        return articles


class MoreePlainsScraper(BaseScraper):
    """
    Scraper for Moree Plains Shire Council media releases (Joomla blog layout).

    Each media release renders as a full-body ``<article>`` on the listing page,
    so the title is a bare ``<h2>`` (no anchor) and the only reliable link is the
    print/email icon href, which carries a ``?tmpl=component&print=1`` query we
    strip to recover the canonical URL. Publish dates are not reliably present in
    the article body (it mixes in submission deadlines and meeting dates), but
    each detail page exposes a Joomla publish date via
    ``time[itemprop=datePublished]``. We follow each article (newest-first,
    capped) to read that date — the same approach as InnerWestScraper.
    """

    ITEM_SELECTOR = 'article'
    MAX_DETAIL_FETCHES = 10

    def __init__(self, council_id: str, council_name: str, news_url: str, **kwargs):
        super().__init__(council_id, council_name, news_url, **kwargs)

    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page(self.news_url)
        if not html:
            return []

        soup = self.parse_html(html)
        articles = []

        for art in soup.select(self.ITEM_SELECTOR):
            heading = art.find(['h1', 'h2', 'h3'])
            if not heading:
                continue
            title = heading.get_text(' ', strip=True)
            if not title:
                continue

            link = None
            for a in art.select('ul.actions a[href]'):
                if '/media-releases/' in a['href']:
                    link = a['href']
                    break
            if not link:
                continue
            link = re.sub(r'\?.*$', '', link)  # drop Joomla print template query

            articles.append(self.create_article(title, link, None))

        # Limit before the (expensive) per-article date fetches.
        cap = self.limit or self.MAX_DETAIL_FETCHES
        articles = articles[:cap]

        for article in articles:
            self._fetch_article_date(article)
            time.sleep(1)  # be polite

        return articles

    def _fetch_article_date(self, article: NewsArticle):
        """Read the Joomla publish date from the article detail page."""
        try:
            html = self.fetch_page(article.url)
            if not html:
                return
            soup = self.parse_html(html)
            date_el = soup.select_one('time[itemprop=datePublished], time[datetime]')
            if date_el:
                # Prefer the ISO datetime attribute; fall back to text like
                # "Published: 07 June 2026". parse_date handles both safely
                # (ISO is parsed without dayfirst to avoid day/month swaps).
                raw = date_el.get('datetime') or date_el.get_text(strip=True)
                article.date = self.parse_date(raw)
        except Exception as e:
            print(f"Error fetching Moree date for {article.url}: {e}")


class DrupalScraper(BaseScraper):
    """
    Scraper for Drupal-based council websites.

    Drupal teasers often lack anchor links on the title, but embed the node ID
    in a ``data-history-node-id`` attribute.  This scraper extracts the node ID
    and constructs the article URL as ``{base_url}/node/{id}``, which Drupal
    then redirects to the clean alias URL.
    """

    def __init__(self, council_id: str, council_name: str, news_url: str, **kwargs):
        super().__init__(council_id, council_name, news_url, **kwargs)

    def scrape(self) -> List[NewsArticle]:
        from bs4 import BeautifulSoup
        from urllib.parse import urlparse

        html = self.fetch_page(self.news_url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        base = "{0.scheme}://{0.netloc}".format(urlparse(self.news_url))
        nodes = soup.select('[data-history-node-id]')
        articles = []

        for node in nodes:
            node_id = node.get('data-history-node-id')
            if not node_id:
                continue

            title_el = node.select_one('.teaser__title, .field--name-title, h2, h3, h4')
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            date_el = node.select_one(
                'time, .field--name-node-post-date, [class*=date-icon], [class*=teaser__date]'
            )
            date_obj = None
            if date_el:
                date_text = date_el.get('datetime') or date_el.get_text(strip=True)
                try:
                    date_obj = date_parser.parse(date_text, dayfirst=True)
                except Exception:
                    pass

            url = f"{base}/node/{node_id}"
            articles.append(self.create_article(title, url, date_obj))

        return articles

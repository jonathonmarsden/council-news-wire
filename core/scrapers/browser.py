"""
Scraper using Playwright for CSR/JS-heavy sites.
"""

from typing import List, Dict, Optional
import time
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin

from .base import BaseScraper, NewsArticle
from core.exceptions import ScrapeError

class BrowserScraper(BaseScraper):
    """
    Scraper using Playwright for CSR/JS-heavy sites.
    """
    
    def __init__(self, council_id: str, council_name: str, news_url: str, selectors: Optional[Dict] = None, block_resources: bool = True, use_default_ua: bool = False, user_agent: Optional[str] = None, **kwargs):
        super().__init__(council_id, council_name, news_url, **kwargs)
        self.selectors = selectors or {}
        self.block_resources = block_resources
        self.use_default_ua = use_default_ua
        self.user_agent = user_agent

    def scrape(self) -> List[NewsArticle]:
        """Scrape using a real browser."""
        articles = []
        url = self.news_url
        
        # Selectors are already normalized by Factory
        container_sel = self.selectors.get('item_selector')
        title_sel = self.selectors.get('title_selector')
        link_sel = self.selectors.get('link_selector')
        date_sel = self.selectors.get('date_selector')
        wait_sel = self.selectors.get('wait_selector', container_sel)
        
        if not container_sel:
            print(f"  Error: No container selector configured for {self.council_name}")
            return []

        print(f"  Browser scraping {url}...")
        
        with sync_playwright() as p:
            # Everything from launch onward sits inside the try so a failure
            # at any point still reaches the finally and closes the browser.
            browser = None
            try:
                browser = p.chromium.launch(
                    headless=True,
                    proxy={"server": self.proxy} if self.proxy else None
                )

                ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                if self.user_agent:
                    ua = self.user_agent
                elif self.use_default_ua:
                    ua = None

                context = browser.new_context(
                    user_agent=ua
                )

                # Block images/fonts to save bandwidth
                # Note: Do keep CSS as it helps some React apps hydrate correctly
                if self.block_resources:
                    context.route("**/*.{png,jpg,jpeg,svg,woff,woff2}", lambda route: route.abort())

                page = context.new_page()

                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                # Wait for content to hydrate
                try:
                    if wait_sel:
                        print(f"  Browser waiting for selector: {wait_sel}")
                        page.wait_for_selector(wait_sel, timeout=30000)
                        time.sleep(2) # Ensure hydration settles
                except Exception:
                   print(f"  Timeout waiting for selector: {wait_sel}")
                   # Proceed anyway, as some items might have loaded
                
                # Evaluate allow us to run JS in the page to extract data cleanly
                items = page.query_selector_all(container_sel)
                if not items:
                    print(f"  Debug: Found 0 items with selector '{container_sel}'")
                
                for item in items:
                    try:
                        title_el = item.query_selector(title_sel) if title_sel else item
                        
                        if link_sel == "self":
                            link_el = item
                        else:
                            link_el = item.query_selector(link_sel) if link_sel else item
                            
                        date_el = item.query_selector(date_sel) if date_sel else None
                        
                        if not title_el:
                            continue
                            
                        title = title_el.inner_text().strip()
                        link = link_el.get_attribute('href')
                        
                        if not link or not title:

                            continue
                            
                        # Resolve relative URLs
                        if not link.startswith('http'):
                            link = urljoin(url, link)
                            
                        date_str = date_el.inner_text().strip() if date_el else None
                        date_obj = self.parse_date(date_str) if date_str else None
                        
                        article = NewsArticle(
                            council_id=self.council_id,
                            council_name=self.council_name,
                            title=title,
                            url=link,
                            date=date_obj,
                            excerpt="" 
                        )
                        articles.append(article)
                        
                    except Exception:
                        continue
                        
            except Exception as e:
                # Browser/navigation failure is a fetch failure, not an empty
                # page — raise so it feeds the failure circuit breaker.
                raise ScrapeError(f"{self.council_id}: browser fetch failed: {e}") from e
            finally:
                if browser:
                    browser.close()

        return articles

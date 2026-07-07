from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from dateutil import parser as date_parser

from .base import BaseScraper, NewsArticle

class CatalystScraper(BaseScraper):
    """
    Scraper for the 'Catalyst' CMS used by many small WA councils.
    
    Identified by the structure:
    <div class="module-list">
      <div class="row">
        <div class="col-sm-5">Image</div>
        <div class="col-sm-7">
           <span class="h5">Posted DD Month YYYY</span>
           <span class="h4 text-primary">Title</span>
           ...
        </div>
      </div>
    </div>
    """

    def __init__(self, council_id: str, council_name: str, news_url: str, 
                 use_curl: bool = False, use_cloudscraper: bool = False, 
                 mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, 
                 limit: Optional[int] = None, proxy: Optional[str] = None, 
                 impersonate: str = "chrome110", **kwargs):
        super().__init__(council_id, council_name, news_url, use_curl, use_cloudscraper, 
                         mobile_mode, limit, proxy, impersonate, **kwargs)
        self.selectors = selectors or {}

    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page_or_raise(self.news_url)

        soup = BeautifulSoup(html, 'html.parser')
        container = soup.select_one('.module-list')
        
        if not container:
            # Fallback: sometimes the container class might be different or missing?
            # But based on 60+ sites, this seems the standard.
            return []
            
        articles = []
        # Find all rows that look like news items
        rows = container.select('.row')
        
        for row in rows:
            # Look for the date and title to confirm it's a news item
            # Date usually in <span class="h5">
            date_el = row.select_one('.h5')
            # Title usually in <span class="h4"> or class "h4"
            title_tag = row.select_one('.h4')
            
            if not title_tag:
                continue
                
            title = title_tag.get_text(strip=True)
            if not title:
                continue

            # Catalyst CMS sometimes puts the date in the h4 or similar class
            # Reject titles that are just "Posted DD Month YYYY"
            if title.lower().startswith('posted ') and any(c.isdigit() for c in title):
                continue
                
            # Date parsing
            date = None
            if date_el:
                date_text = date_el.get_text(strip=True)
                # Strip "Posted " prefix common in this CMS
                clean_date_text = date_text.replace('Posted ', '').strip()
                try:
                    date = date_parser.parse(clean_date_text, dayfirst=True)
                except Exception:
                    pass
            
            # Link extraction
            # Usually <a class="btn btn-primary" ...>Read More</a>
            link_el = row.select_one('a.btn')
            if not link_el:
                # Fallback to any link in the row
                link_el = row.select_one('a')
                
            url = None
            if link_el and link_el.has_attr('href'):
                url = urljoin(self.news_url, link_el['href'])
            
            if not url:
                continue
                
            # Excerpt - usually in a <p>
            excerpt = ""
            p_tag = row.select_one('p')
            if p_tag:
                excerpt = p_tag.get_text(strip=True)

            articles.append(self.create_article(
                title=title,
                url=url,
                date=date,
                excerpt=excerpt or None
            ))
            
        return articles

from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from dateutil import parser as date_parser
import re

from .base import BaseScraper, NewsArticle
from core.exceptions import ScrapeError

class WannerooScraper(BaseScraper):
    """
    Scraper for City of Wanneroo (Jadu CMS).
    """
    def __init__(self, council_id: str, council_name: str, news_url: str, 
                 use_curl: bool = False, use_cloudscraper: bool = False, 
                 mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, 
                 limit: Optional[int] = None, proxy: Optional[str] = None, 
                 impersonate: str = "chrome110", **kwargs):
        super().__init__(council_id, council_name, news_url, use_curl, use_cloudscraper, 
                         mobile_mode, limit, proxy, impersonate, **kwargs)

    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page_or_raise(self.news_url)

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
                # Clean up ordinals (parse_date strips the "Published on" prefix itself)
                clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_text)
                date = self.parse_date(clean_date)

            articles.append(self.create_article(
                title=title,
                url=url,
                date=date,
                excerpt=None
            ))

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
                 impersonate: str = "chrome110", **kwargs):
        # Force use_curl=True and impersonate
        super().__init__(council_id, council_name, news_url, use_curl=True, use_cloudscraper=False, 
                         mobile_mode=mobile_mode, limit=limit, proxy=proxy, impersonate="chrome110", **kwargs)

    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page_or_raise(self.news_url)

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
                # Remove "- X min read" (council-specific; parse_date won't strip this)
                if '-' in date_text:
                    date_text = date_text.split('-')[0].strip()
                date = self.parse_date(date_text)

            excerpt = ""
            excerpt_tag = item.select_one('.card-list__synopsis')
            if excerpt_tag:
                excerpt = excerpt_tag.get_text(strip=True)

            articles.append(self.create_article(
                title=title,
                url=url,
                date=date,
                excerpt=excerpt or None
            ))

        return articles

class ClaremontScraper(BaseScraper):
    """
    Scraper for Town of Claremont.
    """
    def __init__(self, council_id: str, council_name: str, news_url: str, 
                 use_curl: bool = True, use_cloudscraper: bool = False, 
                 mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, 
                 limit: Optional[int] = None, proxy: Optional[str] = None, 
                 impersonate: str = "chrome110", **kwargs):
        super().__init__(council_id, council_name, news_url, use_curl, use_cloudscraper, 
                         mobile_mode, limit, proxy, impersonate, **kwargs)

    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page_or_raise(self.news_url)

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
                date = self.parse_date(date_tag.get_text(strip=True))

            articles.append(self.create_article(
                title=title,
                url=url,
                date=date,
                excerpt=None
            ))

        return articles

class JoondalupScraper(BaseScraper):
    """
    Scraper for City of Joondalup (Kentico AJAX).
    """
    def __init__(self, council_id: str, council_name: str, news_url: str, 
                 use_curl: bool = True, use_cloudscraper: bool = False, 
                 mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, 
                 limit: Optional[int] = None, proxy: Optional[str] = None, 
                 impersonate: str = "chrome110", **kwargs):
        super().__init__(council_id, council_name, news_url, use_curl, use_cloudscraper, 
                         mobile_mode, limit, proxy, impersonate, **kwargs)

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
                raise ScrapeError(
                    f"{self.council_id}: Joondalup API failed with HTTP {response.status_code}"
                )

            data = response.json()
        except ScrapeError:
            raise
        except Exception as e:
            print(f"Error scraping Joondalup: {e}")
            raise ScrapeError(f"{self.council_id}: Joondalup API fetch/parse failed: {e}") from e

        html_content = data.get("htmlResult", "")

        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        articles = []

        # Select items
        items = soup.select('article.card')

        for item in items:
            try:
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
                    # Skip rather than post a literal "No Title" article
                    continue

                date = None
                date_str = item.get('data-datetime')
                if date_str:
                    date = self.parse_date(date_str)

                articles.append(self.create_article(
                    title=title,
                    url=url,
                    date=date,
                    excerpt=None
                ))
            except Exception as e:
                print(f"Error scraping Joondalup: {e}")
                continue

        return articles

class BelmontScraper(BaseScraper):
    """
    Scraper for City of Belmont (API based).
    """
    def __init__(self, council_id: str, council_name: str, news_url: str, 
                 use_curl: bool = False, use_cloudscraper: bool = False, 
                 mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, 
                 limit: Optional[int] = None, proxy: Optional[str] = None, 
                 impersonate: str = "chrome110", **kwargs):
        super().__init__(council_id, council_name, news_url, use_curl, use_cloudscraper, 
                         mobile_mode, limit, proxy, impersonate, **kwargs)

    def scrape(self) -> List[NewsArticle]:
        api_url = "https://www.belmont.wa.gov.au/api/search/search"
        params = {
            "keyword": "",
            "sort": "DATE_DSC",
            "pagenum": 1,
            "path": "",
            "defaultfilters": "",
            "sortfieldname": "menuitemname",
            "pagesize": 12,
            "wrapperclass": "",
            "trunclength": "255",
            "searchindex": "BelmontNewsIndex",
            "transformationname": "Belmont.Transformations.NewsSearchResults",
            "resultprefix": "",
            "resultsuffix": " articles",
            "showdidyoumean": "true",
            "userguid": "3758B9B5-045C-4B7D-B020-80F9B068D990",
            "showresultscount": "false",
            "replacelucenehyphens": "false",
            "filters": ""
        }
        
        try:
            # Update headers for API request
            headers = self.session.headers.copy()
            headers.update({
                "Referer": "https://www.belmont.wa.gov.au/discover/what-s-happening/latest-news",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest"
            })

            # Using self.session to maintain headers/cookies if needed, though mostly stateless API
            response = self.session.get(
                api_url,
                params=params,
                headers=headers,
                timeout=30,
                proxies={'http': self.proxy, 'https': self.proxy} if self.proxy else None
            )
            response.raise_for_status()
            data = response.json()
        except ScrapeError:
            raise
        except Exception as e:
            print(f"Error scraping Belmont: {e}")
            raise ScrapeError(f"{self.council_id}: Belmont API fetch/parse failed: {e}") from e

        articles = []
        if "PartialHTML" in data:
            soup = BeautifulSoup(data["PartialHTML"], "html.parser")
            items = soup.find_all(class_="news-item")

            for item in items:
                try:
                    title_el = item.find(class_="title")
                    if not title_el:
                        continue

                    # Check for strong tag inside title
                    strong = title_el.find("strong")
                    title = strong.get_text(strip=True) if strong else title_el.get_text(strip=True)

                    # Link
                    link = item.find("a")
                    # Fallback if link not found immediately
                    if not link and title_el.name == 'a':
                        link = title_el
                    elif not link:
                        link = item.find(class_="read-more")

                    url = link.get("href") if link else None
                    if url:
                        # Ensure absolute URL
                        if not url.startswith("http"):
                             url = "https://www.belmont.wa.gov.au" + (url if url.startswith("/") else "/" + url)
                    else:
                        continue

                    # Date
                    date_el = item.find(class_="release-date")
                    date_val = None
                    if date_el:
                        date_str = date_el.get_text(strip=True)
                        try:
                            # 16 January 2026
                            date_val = datetime.strptime(date_str, "%d %B %Y")
                        except ValueError:
                            pass

                    excerpt_el = item.find(class_="desc")
                    excerpt = excerpt_el.get_text(strip=True) if excerpt_el else ""

                    articles.append(self.create_article(
                        title=title,
                        url=url,
                        date=date_val,
                        excerpt=excerpt or None
                    ))
                except Exception as e:
                    print(f"Error scraping Belmont: {e}")
                    continue

        return articles

class DumbleyungScraper(BaseScraper):
    """
    Custom scraper for Shire of Dumbleyung.
    They host 'News' on a Wix placeholder page, but 'Newsletters' on Mailchimp.
    This scraper fetches the newsletters page and extracts Mailchimp links.
    """
    def __init__(self, council_id: str, council_name: str, news_url: str, 
                 use_curl: bool = False, use_cloudscraper: bool = False, 
                 mobile_mode: bool = False, selectors: Optional[Dict[str, str]] = None, 
                 limit: Optional[int] = None, proxy: Optional[str] = None, 
                 impersonate: str = "chrome110", **kwargs):
        super().__init__(council_id, council_name, news_url, use_curl, use_cloudscraper, 
                         mobile_mode, limit, proxy, impersonate, **kwargs)

    def scrape(self) -> List[NewsArticle]:
        html = self.fetch_page_or_raise(self.news_url)

        soup = BeautifulSoup(html, 'html.parser')
        articles = []
        
        # Look for mailchimp links in the content
        links = soup.find_all('a', href=re.compile(r'mailchi\.mp'))
        
        seen_urls = set()
        
        for link in links:
            url = link['href']
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            text = link.get_text(strip=True)
            if not text:
                continue
                
            # Parse date from text (e.g. "January 2026")
            date = None
            try:
                # Add a dummy day 1 to parse "Month Year" or similar.
                # Default to the CURRENT year so year-less dates don't get
                # pinned to a hardcoded year forever.
                date = date_parser.parse(text, default=datetime(datetime.now().year, 1, 1))
            except Exception:
                pass

            articles.append(self.create_article(
                title=f"{text} Newsletter",
                url=url,
                date=date,
                excerpt="Dumbleyung Shire Newsletter (Mailchimp)"
            ))
            
        return articles




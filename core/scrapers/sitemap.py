"""
Sitemap scraper, for sites whose news pages render client-side.

Some sites (Wix, for one) build each article in the browser, so the HTML holds
no article list, but they publish an XML sitemap of the article pages with a
last-modified date each. This scraper reads that sitemap, keeps the newest
pages, and takes each page's title from its og:title (which these sites do
render server-side), falling back to the URL slug.

Config:
    news_url      the sitemap URL
    url_contains  only keep <loc> values containing this text (optional)
    limit         how many of the newest pages to title (default 15)

The date is the sitemap's lastmod, which is the last edit rather than first
publication. Posts are deduplicated by URL, so an edit never reposts a page.
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

from .base import BaseScraper, NewsArticle
from core.exceptions import ScrapeError

DEFAULT_LIMIT = 15

# Words kept lower case inside a title-cased headline.
_SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into",
          "of", "on", "or", "the", "to", "with"}


_CITATION = re.compile(r"\b(ACT|REGULATIONS?)\s+\d{4}\b", re.I)


def tidy_title(raw: str, council_name: str = "") -> str:
    """Make an all-capitals, possibly multi-line heading readable.

    Multi-line headings on these sites split the title over lines, sometimes
    stacking the council name and the Acts it is made under on top. Those
    lines are dropped and the rest joined with a dash. All-capitals text is
    title-cased; mixed-case text is left alone.
    """
    lines = [re.sub(r"\s+", " ", l).strip() for l in (raw or "").splitlines()]
    lines = [l for l in lines if l]
    kept = [l for l in lines
            if l.lower() != (council_name or "").lower() and not _CITATION.search(l)]
    title = " - ".join(kept or lines[-1:])
    letters = [c for c in title if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        words = title.lower().split(" ")
        out = []
        for i, w in enumerate(words):
            if i and w in _SMALL:
                out.append(w)
            else:
                # capitalise after leading punctuation and after hyphens/brackets
                out.append(re.sub(r"(^|[-(/\"'\u2018\u201c])([a-z])",
                                  lambda m: m.group(1) + m.group(2).upper(), w))
        title = " ".join(out)
    return title


def title_from_slug(url: str) -> str:
    slug = unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1])
    return tidy_title(re.sub(r"[-_]+", " ", slug).upper())


def parse_sitemap(xml: str, url_contains: Optional[str] = None) -> List[tuple]:
    """(url, lastmod datetime or None) pairs, newest first."""
    soup = BeautifulSoup(xml, "xml")
    out = []
    for u in soup.find_all("url"):
        loc = u.find("loc")
        if not loc:
            continue
        url = loc.get_text(strip=True)
        if url_contains and url_contains not in url:
            continue
        lm = u.find("lastmod")
        when = None
        if lm:
            try:
                when = datetime.fromisoformat(lm.get_text(strip=True)[:10])
            except ValueError:
                when = None
        out.append((url, when))
    out.sort(key=lambda p: p[1] or datetime.min, reverse=True)
    return out


class SitemapScraper(BaseScraper):
    """Articles from an XML sitemap, titled from each page's og:title."""

    def __init__(self, council_id: str, council_name: str, news_url: str, use_curl: bool = False,
                 use_cloudscraper: bool = False, mobile_mode: bool = False, selectors=None,
                 limit: Optional[int] = None, proxy: Optional[str] = None,
                 impersonate: str = "chrome124", url_contains: Optional[str] = None, **kwargs):
        super().__init__(council_id, council_name, news_url, use_curl, use_cloudscraper,
                         mobile_mode, limit, proxy, impersonate, **kwargs)
        self.url_contains = url_contains
        self.max_pages = limit or DEFAULT_LIMIT

    def scrape(self) -> List[NewsArticle]:
        xml = self.fetch_page_or_raise(self.news_url)
        try:
            pages = parse_sitemap(xml, self.url_contains)
        except Exception as e:
            raise ScrapeError(f"{self.council_id}: unreadable sitemap: {e}") from e
        articles = []
        for url, when in pages[: self.max_pages]:
            title = self._page_title(url) or title_from_slug(url)
            if title:
                articles.append(self.create_article(title, url, when, None))
        return articles

    def _page_title(self, url: str) -> str:
        page = self.fetch_page(url)
        if not page:
            return ""
        m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', page)
        return tidy_title(html.unescape(m.group(1)), self.council_name) if m else ""

"""
Custom scraper implementations for specific councils.
"""

import re
import time
from typing import List

from .base import NewsArticle
from .card import CardScraper

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

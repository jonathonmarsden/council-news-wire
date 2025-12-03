"""
DEPRECATED: This module is deprecated. Use core.scrapers instead.
"""

import warnings
from .scrapers import BaseScraper, CardScraper, RSSScraper, InnerWestScraper, ScraperFactory, NewsArticle

warnings.warn(
    "core.scraper is deprecated, use core.scrapers instead",
    DeprecationWarning,
    stacklevel=2
)

__all__ = [
    'BaseScraper',
    'CardScraper',
    'RSSScraper',
    'InnerWestScraper',
    'ScraperFactory',
    'NewsArticle',
]

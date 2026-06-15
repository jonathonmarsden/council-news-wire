"""
Centralized constants for the Council News Bot.
"""
from typing import List, Set

# Phrases that indicate an article is not a news item
GARBAGE_TITLES: Set[str] = {
    'ato image', 
    'no title', 
    'untitled',
    'array'
}

# Generic navigation titles to ignore
GENERIC_TITLES: Set[str] = {
    'home',
    'sitemap',
    'contact us',
    'privacy policy',
    'accessibility',
    'search',
    'news',
    'shire administration office',
    'quick links',
    # "Read more" link text — emitted when a card's real title element is
    # empty and the scraper falls back to the read-more anchor.
    'read more',
    'read moreabout',
    'read more about',
}

# Substrings detection for address-like titles
ADDRESS_MARKERS: List[str] = [
    'street', 'road', 'avenue', ' lot ', 'highway', ' dr ', ' drive'
]

# File system paths
# (Can be expanded later to replace config.py/hardcoded paths)

"""
Utility functions for Council News Bot.
"""

import logging
import sys
from datetime import datetime
from typing import Optional
from dateutil import parser as date_parser

def setup_logging(level=logging.INFO):
    """Configure logging."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse a date string into a datetime object.
    
    Args:
        date_str: Date string to parse
        
    Returns:
        datetime object or None if parsing failed
    """
    if not date_str:
        return None
        
    try:
        return date_parser.parse(date_str, fuzzy=True)
    except (ValueError, TypeError):
        return None

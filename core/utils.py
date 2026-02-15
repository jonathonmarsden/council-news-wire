"""
Utility functions for Council News Bot.
"""

from __future__ import annotations

import logging
import sys
import json
from datetime import datetime
from typing import Optional
from dateutil import parser as date_parser

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name
        }
        if hasattr(record, 'council_id'):
            log_record['council_id'] = record.council_id
        return json.dumps(log_record)

def get_logger(name: str) -> logging.Logger:
    """Get a configured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        # Use simple format for now to keep CLI readable, can switch to JSON later for file logs
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

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
        # Default fuzzy=True is dangerous (parses "40 years" as Year 2040)
        # We add sanity checks
        dt = date_parser.parse(date_str, fuzzy=True)
        
        # Sanity Check 1: Year Range
        # News shouldn't be from the distant past or future
        current_year = datetime.now().year
        if dt.year < 2020 or dt.year > current_year + 2:
            # Allow up to +2 years just in case (e.g. "Events in 2027") 
            # but reject 2030, 2040, 6175 etc.
            return None
            
        return dt
    except (ValueError, TypeError):
        return None

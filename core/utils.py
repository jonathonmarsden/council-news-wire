"""
Utility functions for Council News Bot.
"""

from __future__ import annotations

import html
import logging
import re
import sys
import json
from datetime import datetime

from typing import Optional
from dateutil import parser as date_parser

DEFAULT_MAX_ARTICLE_AGE_DAYS = 7


def max_article_age_days() -> int:
    """How old an article may be and still be posted.

    Seven days by default. After an outage the operator sets
    MAX_ARTICLE_AGE_DAYS in the environment (for example 10 after a
    three-day gap) so the stories that were published while the bot was
    down are relayed instead of archived. Read at call time, not import
    time, so one setting covers the scrape path and the queue path in the
    same run without a restart. Anything unparseable means the default.
    """
    import os
    raw = os.environ.get("MAX_ARTICLE_AGE_DAYS", "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_ARTICLE_AGE_DAYS
    return value if value > 0 else DEFAULT_MAX_ARTICLE_AGE_DAYS


# An entity whose terminating semicolon has gone missing: "&rsquo s",
# "Clare &amp Gilbert". Numeric and named forms, at least two characters so
# that "AT&T" and "R&D" are left alone (and html.unescape rejects any name
# that is not a real entity anyway).
_ENTITY_NO_SEMICOLON = re.compile(r"&(#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]{1,8})\b(?!;)")
# An apostrophe whose lost semicolon became a space, splitting a contraction
# or possessive: "Council’ s", "don’ t", "we’ re". Only those endings.
_SPLIT_APOSTROPHE = re.compile(r"(?<=[A-Za-z])[’'] (?=(?:s|t|re|ve|ll|d|m)(?![\w-]))")


def repair_entities(text: Optional[str]) -> Optional[str]:
    """Decode HTML entities, including ones that have lost their semicolon.

    The LGA SA platform (Squiz) double-encodes its teasers and drops the
    semicolon in the process: the source reads "&amp;rsquo s", a single
    html.unescape leaves "&rsquo s", and the post went out as
    "Council&rsquo s current suite of By-laws". Decode once, then repair any
    semicolon-less entity that html knows: "&rsquo s" -> "'s", "&ndash " ->
    "- ", "Clare &amp Gilbert" -> "Clare & Gilbert". Anything html does not
    recognise ("M&Ms") is left exactly as it was.
    """
    if not text:
        return text
    text = html.unescape(text)

    def _fix(m: "re.Match[str]") -> str:
        name = m.group(1)
        decoded = html.unescape(f"&{name};")
        if decoded == f"&{name};":
            return m.group(0)  # not an entity html knows; leave it
        return decoded

    # html.unescape already accepts numeric references without a semicolon
    # (&#8217 s -> ’ s), so the split-apostrophe repair runs on the decoded
    # text rather than on the entity.
    text = _ENTITY_NO_SEMICOLON.sub(_fix, text)
    return _SPLIT_APOSTROPHE.sub("’", text)


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

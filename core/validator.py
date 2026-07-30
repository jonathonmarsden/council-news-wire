import re
from typing import Dict, List, Tuple, Union

from core.constants import GARBAGE_TITLES, GENERIC_TITLES, ADDRESS_MARKERS

MAX_TITLE_LEN = 250
IDEAL_TITLE_LEN = 120
IDEAL_EXCERPT_LEN = 250
MAX_HASHTAGS = 15
# Routine posts now carry only tags this project owns - its own tag and the
# council's - because at ~8,000 posts a month any community tag would be
# swamped (we would be 98% of #LocalGov, 86% of #NSWpol). Two is therefore the
# normal, intended count; the floor exists only to catch a post that lost its
# tags entirely.
MIN_HASHTAGS = 1

HASHTAG_ORDER = [
    "#LGNewsRoundup",
]

URL_FORBIDDEN_PREFIXES = ("mailto:", "tel:")
URL_BAD_SUBSTRINGS = ["/login", "/signin", "?share=", "utm_source=facebook"]


def is_valid_article(article_obj: Union[dict, object]) -> bool:
    """
    Check if article content looks like a real news item.

    Accepts a NewsArticle object or a plain dict (as stored in the database).
    Returns False for garbage, navigation, address-like, or metadata titles.
    """
    if isinstance(article_obj, dict):
        title = article_obj.get('title')
    else:
        title = getattr(article_obj, 'title', None)

    if not title or not title.strip():
        return False

    # Strip private-use-area characters (icon-font glyphs, e.g.  used
    # for "read more" arrows) before evaluating — they carry no text meaning.
    title = re.sub(r'[-]', '', title).strip()

    if not title:
        return False

    if len(title) < 5:
        return False

    # Reject purely numeric values (e.g. "2026", "6175")
    if title.replace('-', '').replace(' ', '').isdigit():
        return False

    if title.lower() in GENERIC_TITLES:
        return False

    # Reject address-like titles (e.g. "Lot 112 Smith St")
    if title[0].isdigit() and any(x in title.lower() for x in ADDRESS_MARKERS):
        return False

    # Reject metadata titles (e.g. "Posted 04 December 2025")
    if title.lower().startswith('posted ') and any(c.isdigit() for c in title):
        return False

    # Reject copyright footers (e.g. "© 2025 Shire of ...")
    if title.startswith('©') or title.startswith('&copy;'):
        return False

    if title.lower() in GARBAGE_TITLES:
        return False

    return True


def validate_post(text: str, title: str, excerpt: str, url: str, hashtags: List[str], facets: List[Tuple[int, int]]) -> List[str]:
    errors = []

    # Title - Must differ from generic strings
    if not title or len(title.strip()) < 5:
        errors.append("Title too short")
    
    BAD_TITLES = ["Home", "Quick Links", "Contact Us", "Privacy Policy", "Shire Administration Office"]
    if any(t.lower() == title.lower() for t in BAD_TITLES):
        errors.append("Generic title detected")

    if len(title) > MAX_TITLE_LEN:
        errors.append(f"Title too long ({len(title)})")

    # Excerpt (optional)
    if excerpt:
        if len(excerpt) > IDEAL_EXCERPT_LEN:
            errors.append(f"Excerpt too long ({len(excerpt)})")
        if "#" in excerpt or re.search(r"https?://", excerpt):
            errors.append("Excerpt contains hashtags or URLs")

    # URL hygiene
    if not url or not re.match(r"https?://", url):
        errors.append("Invalid or missing URL")
    if url.startswith(URL_FORBIDDEN_PREFIXES):
        errors.append("Forbidden URL scheme")

    if any(bad in url for bad in URL_BAD_SUBSTRINGS):
        errors.append("URL contains forbidden substring")

    # Hashtags
    if not hashtags:
        errors.append("Missing hashtags")
    if hashtags and (len(hashtags) < MIN_HASHTAGS or len(hashtags) > MAX_HASHTAGS):
        errors.append(f"Hashtag count out of range ({len(hashtags)})")

    # Facets: must align to hashtags/URL spans
    text_bytes = text.encode('utf-8')
    byte_len = len(text_bytes)
    for start, end in facets:
        if start < 0 or end <= start or end > byte_len:
            errors.append(f"Facet span invalid ({start}-{end} vs len {byte_len})")

    # Total post length — the one limit BlueSky actually enforces (300
    # graphemes / 3000 UTF-8 bytes). len() counts code points >= graphemes,
    # so this check is safely conservative.
    if len(text) > 300:
        errors.append(f"Post too long ({len(text)} chars > 300)")
    if byte_len > 3000:
        errors.append(f"Post too long ({byte_len} bytes > 3000)")

    return errors

import re
from typing import Dict, List, Tuple

MAX_TITLE_LEN = 150
IDEAL_TITLE_LEN = 120
IDEAL_EXCERPT_LEN = 250
MAX_HASHTAGS = 15
MIN_HASHTAGS = 3

HASHTAG_ORDER = [
    "#LGNewsRoundup",
]

URL_FORBIDDEN_PREFIXES = ("mailto:", "tel:")
URL_BAD_SUBSTRINGS = ["/login", "/signin", "?share=", "utm_source=facebook"]


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

    return errors

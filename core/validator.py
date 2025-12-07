import re
from typing import Dict, List, Tuple

MAX_TITLE_LEN = 150
IDEAL_TITLE_LEN = 120
IDEAL_EXCERPT_LEN = 120
MAX_HASHTAGS = 6
MIN_HASHTAGS = 3

HASHTAG_ORDER = [
    "#LGNewsRoundup",
    "STATE_PEAK",  # replace with mapped state peak
    "STATE_COUNCILS",  # replace with mapped state councils tag
    "COUNCIL_TAG"  # replace with canonical council hashtag
]

URL_FORBIDDEN_PREFIXES = ("mailto:", "tel:")
URL_BAD_SUBSTRINGS = ["/login", "/signin", "?share=", "utm_"]


def validate_post(text: str, title: str, excerpt: str, url: str, hashtags: List[str], facets: List[Tuple[int, int]]) -> List[str]:
    errors = []

    # Title
    if not title or len(title.strip()) == 0:
        errors.append("Missing title")
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
    for start, end in facets:
        if start < 0 or end <= start or end > len(text):
            errors.append("Facet span invalid")

    return errors

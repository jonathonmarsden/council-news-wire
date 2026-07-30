"""Build a Bluesky external link card (app.bsky.embed.external) for an article.

Bluesky does not auto-generate link previews: the posting client must fetch the
target page's OpenGraph tags, upload any thumbnail as a blob, and attach the
embed to the post record itself. This module does that, defensively.

Design contract: this is *additive and never destructive*. If anything is
missing or fails (no OG tags, no image, a 404, a network error), it returns
None and the caller posts exactly the text post it would have posted anyway.
A link card must never make a post worse than the plain-text version.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

try:
    from curl_cffi import requests as _requests
    _IMPERSONATE = {"impersonate": "chrome124"}
except ImportError:  # pragma: no cover - curl_cffi is a hard dep in prod
    import requests as _requests  # type: ignore
    _IMPERSONATE = {}

from bs4 import BeautifulSoup

FETCH_TIMEOUT = 20
MAX_IMAGE_BYTES = 900_000  # Bluesky blob limit is ~1MB; stay safely under
# Site-name cruft commonly SUFFIXED to <title>/og:title by council CMSs,
# e.g. "Arbiter report tabled | City of Ballarat", "… » Shire of X".
_TITLE_SUFFIX = re.compile(
    r"\s*[|»\-–—]\s*(?:[A-Z][\w'&.]*\s*){0,6}"
    r"(?:Council|Shire|City|News|Government|Gov)\b.*$",
    re.IGNORECASE,
)

# Generic labels council CMSs PREFIX onto the real headline, e.g.
# "News Story - MRC Opens …", "Media Release: …", "Latest News | …".
_TITLE_PREFIX = re.compile(
    r"^\s*(?:news story|news release|media release|media statement|latest news"
    r"|council news|news(?:\s*&\s*(?:notices|media))?|announcement|press release)"
    r"\s*[:|»\-–—]\s*",
    re.IGNORECASE,
)


def _meta(soup: BeautifulSoup, *names: str) -> str:
    for n in names:
        tag = soup.find("meta", property=n) or soup.find("meta", attrs={"name": n})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def clean_title(raw: str) -> str:
    """Strip site-name cruft: trailing ('… | City of Ballarat') and leading
    ('News Story - …', 'Media Release: …') generic labels."""
    if not raw:
        return raw
    cleaned = _TITLE_SUFFIX.sub("", raw).strip()
    cleaned = _TITLE_PREFIX.sub("", cleaned).strip()
    # Never strip everything away; fall back to the original if we over-cut.
    return cleaned if len(cleaned) >= 8 else raw.strip()


def fetch_card_data(url: str) -> Optional[dict]:
    """Fetch OG data for `url`. Returns a dict or None if unusable.

    Returns None (caller falls back to text) when: the fetch fails, the page is
    an error page (4xx/5xx), or there is no usable title. An absent image is
    fine - a card with title+description is still worth showing.
    """
    try:
        resp = _requests.get(url, timeout=FETCH_TIMEOUT, **_IMPERSONATE)
    except Exception:
        return None
    if resp.status_code >= 400:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    title = _meta(soup, "og:title", "twitter:title")
    if not title and soup.title:
        title = soup.title.get_text(strip=True)
    title = clean_title(title)
    # Guard against error pages that still return 200.
    if not title or re.search(r"page not found|404|error", title, re.IGNORECASE):
        return None

    description = _meta(soup, "og:description", "twitter:description", "description")
    image = _meta(soup, "og:image", "twitter:image")
    if image:
        image = urljoin(url, image)  # resolve protocol-relative / relative URLs

    return {"uri": url, "title": title[:300], "description": description[:1000], "image": image}


def _download_image(url: str) -> Optional[bytes]:
    try:
        resp = _requests.get(url, timeout=FETCH_TIMEOUT, **_IMPERSONATE)
    except Exception:
        return None
    if resp.status_code >= 400:
        return None
    data = resp.content
    ctype = resp.headers.get("content-type", "")
    if not ctype.startswith("image/") or len(data) > MAX_IMAGE_BYTES or not data:
        return None
    return data


def build_external_embed(client, models, url: str, require_image: bool = True,
                         fallback=None):
    """Return an app.bsky.embed.external for `url`, or None to fall back to text.

    `client` is an authenticated atproto Client (for uploadBlob); `models` is
    the atproto models module. Any failure returns None - never raises into
    the posting path.

    require_image (default True): only produce a card when a real thumbnail
    was fetched and uploaded. An image-less card is a title+description box
    with no picture, which can look emptier than the plain text post; with
    require_image, those simply fall back to text. Set False to allow
    text-cards (title/description, no thumb).

    fallback: optional zero-argument callable returning PNG bytes to use as the
    thumbnail when the council's site offers no usable image. This is how
    small-shire stories still get a card - a branded one we render ourselves -
    instead of posting as a bare link.
    """
    try:
        data = fetch_card_data(url)
        if not data:
            return None

        thumb = None
        if data["image"]:
            img_bytes = _download_image(data["image"])
            if img_bytes:
                try:
                    thumb = client.upload_blob(img_bytes).blob
                except Exception:
                    thumb = None  # image failed -> treat as no image below

        generated = False
        if thumb is None and fallback is not None:
            try:
                png = fallback()
                if png:
                    thumb = client.upload_blob(png).blob
                    generated = True
            except Exception:
                thumb = None

        if thumb is None and require_image:
            return None  # no usable thumbnail -> fall back to clean text post

        external = models.AppBskyEmbedExternal.External(
            uri=data["uri"],
            title=data["title"],
            description=data["description"],
            thumb=thumb,
        )
        embed = models.AppBskyEmbedExternal.Main(external=external)
        # How the thumbnail was obtained, for the caller to persist as
        # image_status: 'generated' means we rendered a branded fallback.
        try:
            embed.lgnews_image_status = "generated" if generated else "image"
        except Exception:
            pass  # pydantic models may forbid extra attrs; status is optional
        return embed
    except Exception:
        return None

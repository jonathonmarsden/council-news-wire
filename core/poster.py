"""
BlueSky posting functionality for Council News Bot.

Handles authentication and posting news articles to BlueSky.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from datetime import datetime
from typing import Optional, List, Dict, Any

from atproto import Client, models

from core.exceptions import TransientPostError
from core.validator import validate_post

# --- Hashtags -------------------------------------------------------------
#
# Measured on 2026-07-30 by searching Bluesky for each tag and checking who was
# posting in it. The peak-body and "<State>Councils" tags we had been using were
# almost entirely our own output - #VLGA 100% self, #LGNSW 100%, #VicCouncils
# 96%, #MAV 92% - so five tags per post were reaching no one outside this
# network, while tags with real communities went unused.
#
# Tags with genuine external audiences (monthly post volume, ~0% ours):
#   #Auspol 10,000+   #LocalNews 697   #QldPol 604   #NSWpol 350
#   #SpringSt 256     #LocalGov 158
#
# #Auspol is deliberately NOT used here. At ~536 posts a day this feed would
# swamp it many times over, which is both antisocial and the pattern spam
# heuristics look for. It is reserved for occasional curated amplification from
# the personal account, chosen by measured engagement.
#
# Kept per routine post: one real sector community (#LocalGov), one live state
# politics community, and the project's own tag for archive/branding.
# Override with LGNEWS_TAGS_<STATE> (comma-separated) to retune without a deploy.
BRAND_TAG = '#LGNewsRoundup'

# Routine posts carry no community hashtags at all, and the arithmetic is the
# reason. This network publishes ~8,000 posts a month. Measured tag volumes are
# tiny beside that, so using them would not be participating in a community -
# it would be replacing it:
#
#   #LocalGov 158/mo  -> we would be 98% of the tag
#   #WApol    101/mo  -> 93%      #SpringSt 256/mo -> 88%
#   #NSWpol   350/mo  -> 86%      #QldPol   604/mo -> 70%
#   #Auspol 10,000/mo -> 44%
#
# A tag belongs to the people already in it. Staying under roughly 5-10% of its
# volume would need a tag with 80,000+ posts a month; no Australian tag is that
# large. So the firehose carries only tags we own - the project's own tag and
# the council's - which nobody else posts in and which make the archive
# searchable per council. Community tags are reserved for occasional curated
# amplification from the personal account (see scripts/monitoring/
# amplify_candidates.py), where the volume is a handful a day rather than
# hundreds.
STATE_TAGS = {s: [] for s in
              ('NSW', 'VIC', 'QLD', 'SA', 'WA', 'TAS', 'NT', 'ACT', 'NAT')}

# Retained for backwards compatibility: other modules and tests import these.
# No longer added to routine posts (see the note above on self-generated reach).
STATE_PEAK_BODIES = {
    'NSW': ['#LGNSW'], 'VIC': ['#VLGA', '#MAV'], 'QLD': ['#LGAQ'],
    'SA': ['#LGASA'], 'WA': ['#WALGA'], 'TAS': ['#LGAT'], 'NT': ['#LGANT'],
    'ACT': [], 'NAT': ['#ALGA'],
}

STATE_COUNCILS_TAG = {
    'NSW': '#NSWCouncils', 'VIC': '#VicCouncils', 'QLD': '#QldCouncils',
    'SA': '#SACouncils', 'WA': '#WACouncils', 'TAS': '#TasCouncils',
    'NT': '#NTCouncils', 'ACT': '', 'NAT': '',
}


MIN_LEDE_LEN = 60          # shorter than this reads as a fragment, not a lede
MAX_LEDE_LEN = 220         # leave room for date, council and tags


def _first_sentence(text: Optional[str]) -> Optional[str]:
    """Return the opening sentence of `text`, or None if it isn't usable.

    Council excerpts are inconsistent: some are a full paragraph, some a
    truncated fragment ending in an ellipsis, some just repeat the headline.
    Only a sentence that stands on its own is worth leading a post with;
    anything else falls back to the headline.
    """
    if not text:
        return None
    clean = " ".join(text.strip().split())
    if not clean or clean.startswith("..."):
        return None
    # Split on sentence enders, keeping abbreviations like "Cr." intact by
    # requiring a following space and capital or end-of-string.
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z"‘“])', clean)
    first = parts[0].strip() if parts else clean
    # A truncated scrape ("... more") is not a sentence.
    if first.endswith("...") or first.endswith("…"):
        first = first.rstrip(".…").strip()
        if not first:
            return None
    if len(first) < MIN_LEDE_LEN:
        # Too short to stand alone; try the first two sentences together.
        if len(parts) > 1:
            joined = f"{first} {parts[1].strip()}".strip()
            if MIN_LEDE_LEN <= len(joined) <= MAX_LEDE_LEN:
                return joined
        return None
    if len(first) > MAX_LEDE_LEN:
        cut = first[:MAX_LEDE_LEN].rsplit(" ", 1)[0].rstrip(",;:")
        return cut + "..." if cut else None
    return first


def _is_own_tag(tag: str, council_name: str = "") -> bool:
    """True if `tag` is one this project owns rather than a shared community.

    Owned tags are the project's own (#LGNewsRoundup) and per-council tags
    (#BathurstRegionalCouncil): nobody else posts in them, so publishing at
    volume floods no one. Everything else - peak bodies, state politics,
    #LocalGov, #Auspol - belongs to other people.
    """
    t = (tag or "").lstrip("#").lower()
    if not t:
        return False
    if t == BRAND_TAG.lstrip("#").lower():
        return True
    # A council tag is the council's name with the spaces removed.
    if council_name:
        if t == re.sub(r"[^a-z0-9]", "", council_name.lower()):
            return True
    return t.endswith("council") or t.endswith("shire") or t.endswith("citycouncil")


def tags_for_state(state: str) -> List[str]:
    """Hashtags for a routine post from `state`, brand tag first.

    LGNEWS_TAGS_<STATE> overrides the defaults, e.g. LGNEWS_TAGS_VIC="#LocalGov,#Melbourne".
    Set it to an empty string to post with the brand tag only.
    """
    code = (state or 'NAT').upper()
    override = os.environ.get(f'LGNEWS_TAGS_{code}')
    if override is not None:
        extra = [t.strip() for t in override.split(',') if t.strip()]
    else:
        extra = list(STATE_TAGS.get(code, STATE_TAGS['NAT']))
    tags = [BRAND_TAG]
    for t in extra:
        tag = t if t.startswith('#') else f'#{t}'
        if tag not in tags:
            tags.append(tag)
    return tags

class BlueSkyPoster:
    """Posts council news articles to BlueSky."""
    
    # Maximum post length for BlueSky
    MAX_POST_LENGTH = 300
    
    def __init__(self, handle: str, password: str, state_code: Optional[str] = None):
        """
        Initialize the BlueSky poster.

        Args:
            handle: BlueSky handle
            password: BlueSky app password
            state_code: explicit state ('VIC', 'NSW', ...). Falls back to
                deriving it from the handle prefix — which silently degrades
                every post to national hashtags if the handles are ever
                renamed, so pass it explicitly where known.
        """
        self.handle = handle
        self.password = password
        self.client = None
        self._authenticated = False
        # Metadata from the most recent successful post (URI/CID, OG data,
        # image_status), for the caller to persist alongside the article.
        self.last_post_meta: Dict[str, Any] = {}
        code = (state_code or '').upper()
        self.state = code if code in STATE_PEAK_BODIES else self._detect_state(handle)

    def _sentence_first_enabled(self) -> bool:
        """True if this feed leads posts with a sentence instead of the headline.

        Measured on Bluesky (2026-07-30), every high-engagement news bot -
        unofficial ABC (12.8k followers, 3.50 eng/post), SBS (3.72), BBC UK
        (2.36) - writes the story's opening sentence as the post text and lets
        the card carry the headline. Ours did the reverse, printing the
        headline in the text and again on the card.

        Controlled by SENTENCE_FIRST_STATES (comma-separated codes, or ALL);
        unset means off, so this can be trialled on a few feeds and compared.
        """
        raw = (os.environ.get("SENTENCE_FIRST_STATES") or "").strip().upper()
        if not raw:
            return False
        if raw == "ALL":
            return True
        return self.state in {c.strip() for c in raw.split(",") if c.strip()}

    def _link_cards_enabled(self) -> bool:
        """True if this feed's state is opted into rich link cards.

        Controlled by the LINK_CARDS_STATES env var: a comma-separated list of
        state codes (e.g. "NT,ACT"), or "ALL" for every feed. Empty/unset means
        off everywhere - the safe default while the feature is a prototype.
        """
        raw = (os.environ.get("LINK_CARDS_STATES") or "").strip().upper()
        if not raw:
            return False
        if raw == "ALL":
            return True
        return self.state in {c.strip() for c in raw.split(",") if c.strip()}

    def _detect_state(self, handle: str) -> str:
        """Derive state code from handle."""
        if not handle: return 'NAT'
        match = re.search(r'roundupnewsbot([a-z]+)', handle.lower())
        if match:
            code = match.group(1).upper()
            if code in STATE_PEAK_BODIES:
                return code
        return 'NAT'
    
    def authenticate(self) -> bool:
        """
        Authenticate with BlueSky.
        
        Returns:
            True if authentication successful, False otherwise
        """
        if not self.handle or not self.password:
            print("Error: BlueSky credentials not configured")
            return False
        
        try:
            self.client = Client()
            self.client.login(self.handle, self.password)
            self._authenticated = True
            print(f"Authenticated as {self.handle}")
            return True
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    
    def post_article(self, council_name: str, title: str, url: str, 
                     date: Optional[datetime] = None, excerpt: Optional[str] = None,
                     hashtags: List[str] = None, council_hashtag: Optional[str] = None) -> Optional[str]:
        """
        Post a news article to BlueSky.
        
        Args:
            council_name: Name of the council
            title: Article title
            url: Article URL
            date: Publication date (optional)
            excerpt: Article excerpt/subtitle (optional)
            hashtags: List of hashtags to include
            
        Returns:
            Post URI if posted successfully, None if the article itself was
            rejected (validation / API 4xx) and should never be retried.

        Raises:
            TransientPostError: on retryable failures (auth/session, network,
            rate limit, 5xx) — the article should stay queued.
        """
        if not self._authenticated:
            if not self.authenticate():
                raise TransientPostError("BlueSky authentication failed")
        
        # SAFETY VALVE: Clean and validate title before posting
        title = self._sanitize_title(title)
        
        if len(title) > 250:
            print(f"Skipping post: Title too long ({len(title)} chars). Check scraper for {council_name}.")
            return None
        
        # Build the link card first: whether one is attached decides how much
        # text the post needs. A card already shows the headline, summary and
        # source, so duplicating them below it just repeats the same words.
        embed = None
        card_data = None
        if self._link_cards_enabled():
            from core.link_card import build_external_embed, fetch_card_data
            from core.card_image import render_card
            card_data = fetch_card_data(url)

            def _branded_card():
                # Councils whose sites expose no og:image still get a card,
                # rendered in the account's own visual language.
                return render_card(
                    title=(card_data or {}).get("title") or title,
                    council_name=council_name,
                    state=self.state,
                    date_str=date.strftime("%d %B %Y") if date else "",
                    subtitle=(card_data or {}).get("description") or "",
                )

            embed = build_external_embed(self.client, models, url,
                                         fallback=_branded_card)

        # Format the post text and get facets for clickable links
        post_text, facets, tags_list, used_excerpt = self._format_post_with_facets(
            council_name, title, url, date, excerpt, hashtags, council_hashtag,
            has_card=embed is not None
        )

        # Build simple facet spans for validation (byte offsets in text)
        facet_spans = []
        for facet in facets:
            try:
                facet_spans.append((facet.index.byte_start, facet.index.byte_end))
            except Exception:
                continue

        # Run validator to catch malformed posts before sending
        validation_errors = validate_post(post_text, title, used_excerpt, url, tags_list, facet_spans)
        if validation_errors:
            # RETRY LOGIC: If validation failed on excerpt, try dropping it
            if any("Excerpt" in err for err in validation_errors):
               print(f"Validation failed on excerpt for {council_name} ('{'; '.join(validation_errors)}'). Retrying without excerpt.")
               # Regenerate without excerpt
               post_text, facets, tags_list, used_excerpt = self._format_post_with_facets(
                    council_name, title, url, date, None, hashtags, council_hashtag
                )
               # Re-calculate facets
               facet_spans = []
               for facet in facets:
                    try:
                        facet_spans.append((facet.index.byte_start, facet.index.byte_end))
                    except Exception:
                        continue
               # Re-validate
               validation_errors = validate_post(post_text, title, used_excerpt, url, tags_list, facet_spans)

            if validation_errors:
                print(f"Skipping post: Validation failed for {council_name} ({'; '.join(validation_errors)})")
                return None
        
        try:
            if embed is not None:
                response = self.client.send_post(text=post_text, facets=facets, embed=embed)
            else:
                response = self.client.send_post(text=post_text, facets=facets)
            post_uri = response.uri
            # Record where and how this went out so callers can persist it.
            # Without the URI, finding a story's own post again means scraping
            # the public feed and matching on title.
            self.last_post_meta = {
                'bluesky_uri': post_uri,
                'bluesky_cid': getattr(response, 'cid', None),
                'og_image_url': (card_data or {}).get('image') or None,
                'og_description': (card_data or {}).get('description') or None,
                'image_status': (getattr(embed, 'lgnews_image_status', 'image')
                                 if embed is not None
                                 else 'none' if card_data is None
                                 else 'failed'),
            }
            print(f"Posted{' [card]' if embed is not None else ''}: {title[:50]}...")
            return post_uri
        except Exception as e:
            # Only a definitive API rejection of this record is permanent.
            # 401 (expired session), 408, 429 and everything without a status
            # (network errors, timeouts, 5xx) are retryable.
            status = getattr(getattr(e, 'response', None), 'status_code', None)
            if status is not None and 400 <= status < 500 and status not in (401, 408, 429):
                print(f"Failed to post (rejected by API, HTTP {status}): {e}")
                return None
            raise TransientPostError(f"send_post failed ({status or type(e).__name__}): {e}") from e
    
    def _sanitize_title(self, title: str) -> str:
        """
        Clean and sanitize title to prevent malformed posts.
        
        - Removes newlines (takes first line only)
        - Strips date patterns from start
        - Removes excessive whitespace
        """
        if not title:
            return ""
        
        # Auto-repair multiline titles - take first line only
        if "\n" in title:
            title = title.split("\n")[0].strip()
        
        # Remove common date patterns from start of title
        # Patterns like "Fri 28 November", "03 December 2025", etc.
        import re
        date_patterns = [
            r'^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?\s+[a-zA-Z]+\s+\d{4}\s*[-–:]*\s*',  # "Tuesday 20 January 2026" or "Tue 20 Jan 2026"
            r'^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?\s+[a-zA-Z]+\s*[-–:]*\s*',  # "Fri 28 November"
            r'^\d{1,2}(?:st|nd|rd|th)?\s+[a-zA-Z]+\s+\d{4}\s*[-–:]*\s*',  # "03 December 2025" or "03 December 2025 - "
            r'^Published on \d{1,2} \w+ \d{4}\s*',  # "Published on 05 December 2025"
            r'^\d{4}-\d{2}-\d{2}\s*[-–:]*\s*', # "2026-01-20 - "
        ]
        for pattern in date_patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        # Handle concatenated patterns like "TitlePublished on 05 December 2025Body..."
        # Split at "Published on" or date patterns appearing mid-string
        mid_patterns = [
            r'Published on \d{1,2} \w+ \d{4}.*$',  # "Published on 05 December 2025..."
            r'\s+\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\s+[A-Z].*$',  # " 4 December 2025 Thirty..."
        ]
        for pattern in mid_patterns:
            match = re.search(pattern, title, flags=re.IGNORECASE)
            if match:
                title = title[:match.start()].strip()
        
        # Clean up whitespace
        title = ' '.join(title.split())
        
        return title.strip()
    
    def _council_to_hashtag(self, council_name: str) -> str:
        """
        Convert council name to hashtag format.
        
        E.g., "Cardinia Shire Council" -> "#CardiniaShireCouncil"
        """
        # Remove special characters and spaces, keep alphanumeric
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', council_name)
        # Convert to PascalCase by capitalizing each word and joining
        words = cleaned.split()
        hashtag = ''.join(word.capitalize() for word in words)
        return f"#{hashtag}"
    
    def _add_tracking_params(self, url: str) -> str:
        """
        Add UTM tracking parameters to the URL.
        
        Promotes the sponsor (LG News Roundup) and identifies the specific feed.
        """
        if not url:
            return url
            
        # Per policy: Promote sponsor and identify feed
        params = {
            "utm_source": "lgnewsroundup.com",
            "utm_medium": "social",
            "utm_campaign": "lg_news_roundup",
            "utm_content": self.handle or "unknown-feed"
        }
        
        try:
            # Parse existing URL
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query)
            
            # Merge new params (overwrite standard UTMs if present to ensure consistency)
            for k, v in params.items():
                query[k] = [v]
                
            # Rebuild
            new_query = urllib.parse.urlencode(query, doseq=True)

            # Ensure path is properly encoded (handles Unicode chars like ’ and –)
            # Unquote first to avoid double-encoding if already encoded
            safe_path = urllib.parse.quote(urllib.parse.unquote(parsed.path), safe='/')
            
            new_url = urllib.parse.urlunparse(parsed._replace(query=new_query, path=safe_path))
            return new_url
        except Exception as e:
            print(f"Error adding UTM params: {e}")
            return url

    def _format_post_with_facets(self, council_name: str, title: str, url: str,
                                  date: Optional[datetime] = None,
                                  excerpt: Optional[str] = None,
                                  extra_hashtags: List[str] = None,
                                  council_hashtag: Optional[str] = None,
                                  has_card: bool = False) -> tuple:
        """
        Format the post text and generate facets for links/hashtags.

        Without a card:
            [Title] (linked)
            [Excerpt]
            [Date]
            [Council Name]
            [Hashtags]

        With a card (has_card=True) the card already shows the headline, the
        summary and the source domain, so repeating them puts the same words on
        screen twice. The text is reduced to the attribution the card does not
        carry - which council, and when - and the headline stays clickable
        there for anyone whose client does not render embeds.
        """
        # 0. Enrich URL with UTM
        final_url = self._add_tracking_params(url)

        # 1. Lede. With a card attached, the card already prints the headline,
        # so repeating it in the text wastes the most valuable line of the
        # post. Every high-engagement news bot measured on Bluesky instead
        # opens with the story's first sentence and lets the card carry the
        # headline. We do the same when a sentence is available; without one
        # (many councils publish no summary) we fall back to the headline,
        # which is better than opening with nothing.
        lede = title
        if has_card and self._sentence_first_enabled():
            sentence = _first_sentence(excerpt)
            if sentence:
                lede = sentence
                excerpt = None  # the sentence IS the text now
        post_title = f"{lede}\n"
        
        # 2. Council Name
        council_line = f"{council_name}\n"
        
        # 3. Date
        date_line = ""
        if date:
            date_line = f"{date.strftime('%d %B %Y')}\n"
        
        # 4. Hashtags — only tags we own: the project's own tag and the
        # council's. See the note by STATE_TAGS for why no community tag can
        # ride on a feed of this volume.
        tags_list = tags_for_state(self.state)
        c_tag = council_hashtag or self._council_to_hashtag(council_name)
        if c_tag and c_tag not in tags_list:
            tags_list.append(c_tag)

        # Extra topics from the caller, filtered to tags we own. State configs
        # still carry legacy community tags (#VLGA, #NSWCouncils); silently
        # dropping them here keeps a stale config from re-flooding a tag.
        if extra_hashtags:
            for t in extra_hashtags:
                if t not in tags_list and _is_own_tag(t, council_name):
                    tags_list.append(t)
        
        hashtags_str = " ".join(tags_list)
        
        # Calculate remaining space for excerpt
        # Fixed parts length (Title + Date + Council + Hashtags)
        fixed_len = len(post_title) + len(date_line) + len(council_line) + len(hashtags_str) + 2 # +2 for newlines
        remaining = self.MAX_POST_LENGTH - fixed_len
        
        # 5. Excerpt — omitted when a card is attached, since the card already
        # shows the same summary directly beneath this text.
        excerpt_text = ""
        if has_card:
            excerpt = None
        # Improved logic: Prioritize excerpt inclusion
        if excerpt and remaining > 50: # Ensure we have reasonable space
            clean_excerpt = excerpt.strip().replace('\n', ' ')
            # Truncate at a word boundary — a raw slice can cut mid-word or
            # even mid-emoji (splitting a ZWJ sequence renders garbage)
            if len(clean_excerpt) > remaining:
                cut = clean_excerpt[:remaining - 4]
                if ' ' in cut:
                    cut = cut.rsplit(' ', 1)[0]
                excerpt_text = cut + "..."
            else:
                excerpt_text = clean_excerpt
            excerpt_text += "\n"
        
        # Construct full text
        # Title\nExcerpt\nDate\nCouncil\nHashtags
        full_text = post_title + excerpt_text + date_line + council_line + hashtags_str
        
        # Ensure we are strictly under the limit
        if len(full_text) > self.MAX_POST_LENGTH:
             # If still too long, drop the excerpt entirely
             excerpt_text = ""
             full_text = post_title + date_line + council_line + hashtags_str
             # If STILL too long, truncate title
             if len(full_text) > self.MAX_POST_LENGTH:
                 overage = len(full_text) - self.MAX_POST_LENGTH
                 new_title_len = len(post_title) - overage - 4 # -4 for safety/ellipsis
                 cut = post_title[:new_title_len]
                 if ' ' in cut:
                     cut = cut.rsplit(' ', 1)[0]
                 post_title = cut + "...\n"
                 full_text = post_title + date_line + council_line + hashtags_str

        # Create Facets
        facets = []
        
        # Link Facet for Title
        # Title is at the start.
        title_text = post_title.strip()
        title_byte_len = len(title_text.encode('utf-8'))
        
        facets.append(models.AppBskyRichtextFacet.Main(
            features=[models.AppBskyRichtextFacet.Link(uri=final_url)],
            index=models.AppBskyRichtextFacet.ByteSlice(byte_start=0, byte_end=title_byte_len)
        ))
        
        # Hashtag Facets — only within the hashtags block at the end. A '#'
        # inside the title would otherwise get a Tag facet overlapping the
        # title's Link facet, which renders unpredictably on clients.
        hashtags_char_start = len(full_text) - len(hashtags_str)
        for match in re.finditer(r'#[a-zA-Z0-9_]+', full_text):
            if match.start() < hashtags_char_start:
                continue
            tag = match.group(0)[1:] # remove #
            start = match.start()
            end = match.end()
            
            # Convert char indices to byte indices
            # This is inefficient but safe: encode substring before the match
            pre_bytes = full_text[:start].encode('utf-8')
            match_bytes = full_text[start:end].encode('utf-8')
            
            byte_start = len(pre_bytes)
            byte_end = byte_start + len(match_bytes)
            
            facets.append(models.AppBskyRichtextFacet.Main(
                features=[models.AppBskyRichtextFacet.Tag(tag=tag)],
                index=models.AppBskyRichtextFacet.ByteSlice(byte_start=byte_start, byte_end=byte_end)
            ))
            
        return full_text, facets, tags_list, excerpt_text.strip()


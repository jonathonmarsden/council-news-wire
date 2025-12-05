"""
BlueSky posting functionality for Council News Bot.

Handles authentication and posting news articles to BlueSky.
"""

import os
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

from atproto import Client, models


class BlueSkyPoster:
    """Posts council news articles to BlueSky."""
    
    # Maximum post length for BlueSky
    MAX_POST_LENGTH = 300
    
    def __init__(self, handle: str, password: str):
        """
        Initialize the BlueSky poster.
        
        Args:
            handle: BlueSky handle
            password: BlueSky app password
        """
        self.handle = handle
        self.password = password
        self.client = None
        self._authenticated = False
    
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
                     hashtags: List[str] = None) -> bool:
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
            True if posted successfully, False otherwise
        """
        if not self._authenticated:
            if not self.authenticate():
                return False
        
        # Format the post text and get facets for clickable links
        post_text, facets = self._format_post_with_facets(council_name, title, url, date, excerpt, hashtags)
        
        try:
            self.client.send_post(text=post_text, facets=facets)
            print(f"Posted: {title[:50]}...")
            return True
        except Exception as e:
            print(f"Failed to post: {e}")
            return False
    
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
    
    def _format_post_with_facets(self, council_name: str, title: str, url: str,
                                  date: Optional[datetime] = None, 
                                  excerpt: Optional[str] = None,
                                  extra_hashtags: List[str] = None) -> tuple:
        """
        Format the post text and generate facets for links/hashtags.
        
        Format:
        [Title] (Linked)
        [Excerpt]
        [Date]
        [Council Name]
        [Hashtags]
        """
        # 1. Title
        post_title = f"{title}\n"
        
        # 2. Council Name
        council_line = f"{council_name}\n"
        
        # 3. Date
        date_line = ""
        if date:
            date_line = f"{date.strftime('%d %B %Y')}\n"
        
        # 4. Hashtags
        council_tag = self._council_to_hashtag(council_name)
        # Create a copy of the list to avoid modifying the original reference
        tags_list = list(extra_hashtags) if extra_hashtags else ["#LocalGov"]
        if council_tag not in tags_list:
            tags_list.append(council_tag)
        
        hashtags_str = " ".join(tags_list)
        
        # Calculate remaining space for excerpt
        # Fixed parts length (Title + Date + Council + Hashtags)
        fixed_len = len(post_title) + len(date_line) + len(council_line) + len(hashtags_str) + 2 # +2 for newlines
        remaining = self.MAX_POST_LENGTH - fixed_len
        
        # 5. Excerpt
        excerpt_text = ""
        if excerpt and remaining > 20:
            # Truncate excerpt if needed
            if len(excerpt) > remaining:
                excerpt_text = excerpt[:remaining-3] + "..."
            else:
                excerpt_text = excerpt
            excerpt_text += "\n"
        
        # Construct full text
        # Title\nExcerpt\nDate\nCouncil\nHashtags
        full_text = post_title + excerpt_text + date_line + council_line + hashtags_str
        
        # Ensure we are strictly under the limit
        if len(full_text) > self.MAX_POST_LENGTH:
             # If still too long, drop the excerpt entirely
             full_text = post_title + date_line + council_line + hashtags_str
             # If STILL too long, truncate title
             if len(full_text) > self.MAX_POST_LENGTH:
                 overage = len(full_text) - self.MAX_POST_LENGTH
                 new_title_len = len(post_title) - overage - 4 # -4 for safety/ellipsis
                 post_title = post_title[:new_title_len] + "...\n"
                 full_text = post_title + date_line + council_line + hashtags_str

        # Create Facets
        facets = []
        
        # Link Facet for Title
        # The title is at the start of the string
        # We need to be careful. atproto expects byte indices relative to the full utf-8 encoded string.
        
        # Title is at the start.
        title_text = post_title.strip()
        title_byte_len = len(title_text.encode('utf-8'))
        
        facets.append(models.AppBskyRichtextFacet.Main(
            features=[models.AppBskyRichtextFacet.Link(uri=url)],
            index=models.AppBskyRichtextFacet.ByteSlice(byte_start=0, byte_end=title_byte_len)
        ))
        
        # Hashtag Facets
        # We need to find each hashtag in the text and create a facet
        # Simple regex for hashtags
        for match in re.finditer(r'#[a-zA-Z0-9_]+', full_text):
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
            
        return full_text, facets


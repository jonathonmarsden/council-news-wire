"""
Bluesky Bookmark Maintenance Tool
=================================

This script implements a workflow for fixing broken or malformed posts using Bluesky bookmarks.

Workflow:
1. The user bookmarks a problematic post (e.g. duplicate, bad formatting, wrong link).
2. This script fetches the user's bookmarks using undocumented XRPC endpoints.
3. It identifies the original council and article.
4. It re-scrapes the council website to get fresh, correct data.
5. It reposts the article using the correct Bot account.
6. It deletes the old broken post and the bookmark.

Undocumented API Endpoints Used:
- app.bsky.bookmark.getBookmarks (Query)
- app.bsky.bookmark.deleteBookmark (Procedure)
"""

import os
import sys
import re
import time
from datetime import datetime
from dotenv import load_dotenv
from atproto import Client, models
import json
from urllib.parse import urlparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import load_state_config, get_scraper
from core.poster import BlueSkyPoster

class ParamsModel:
    """
    A mock model to satisfy atproto library requirements.
    
    The atproto client's `_invoke` method expects input parameters to be 
    Pydantic models or objects with `model_dump` methods. Since we are 
    using undocumented endpoints without official models, we use this 
    wrapper to pass raw dictionaries.
    """
    def __init__(self, data):
        self.data = data
    def model_dump(self, exclude_none=True, by_alias=True):
        return self.data
    def model_dump_json(self, exclude_none=True, by_alias=True):
        return json.dumps(self.data)

def get_council_from_text(text, councils):
    """
    Attempt to identify the council from the post text.
    
    Args:
        text (str): The text content of the post.
        councils (list): List of council configuration dictionaries.
        
    Returns:
        dict or None: The matching council config or None.
    """
    # Try to match council name in text
    for council in councils:
        if council['name'] in text:
            return council
    
    # Future improvement: Add fuzzy matching or hashtag parsing here if needed.
    return None

def fix_and_repost():
    """
    Main execution function.
    Iterates through bookmarks, fixes posts, and cleans up.
    """
    load_dotenv()
    
    # User credentials (The human operator's account)
    user_handle = os.environ.get('BLUESKY_HANDLE_DEBUG', "jonathonmarsden.com")
    user_password = os.environ.get('BLUESKY_PASSWORD_DEBUG', "***REMOVED***")
    
    # Bot credentials configuration
    bots = {
        'VIC': {
            'handle': os.environ.get('BLUESKY_HANDLE_VIC'),
            'password': os.environ.get('BLUESKY_PASSWORD_VIC'),
            'poster': None
        },
        'NSW': {
            'handle': os.environ.get('BLUESKY_HANDLE_NSW'),
            'password': os.environ.get('BLUESKY_PASSWORD_NSW'),
            'poster': None
        },
        'QLD': {
            'handle': os.environ.get('BLUESKY_HANDLE_QLD'),
            'password': os.environ.get('BLUESKY_PASSWORD_QLD'),
            'poster': None
        }
    }
    
    # Load all councils from config files
    all_councils = []
    for state in ['vic', 'nsw', 'qld']:
        data = load_state_config(state)
        for c in data['councils']:
            c['state'] = state.upper()
            all_councils.append(c)
            
    print(f"Loaded {len(all_councils)} councils.")
    
    # Authenticate User
    print(f"\n--- Authenticating as {user_handle} ---")
    user_client = Client()
    user_client.login(user_handle, user_password)
    print("Authenticated.")
    
    # --- Fetch Bookmarks ---
    print("Fetching bookmarks...")
    bookmarks = []
    cursor = None
    while True:
        try:
            print(f"Requesting bookmarks batch... Cursor: {cursor}")
            # Use ParamsModel to pass the query parameters
            params = ParamsModel({'limit': 100, 'cursor': cursor} if cursor else {'limit': 100})
            
            # Call undocumented endpoint: app.bsky.bookmark.getBookmarks
            response = user_client.invoke_query('app.bsky.bookmark.getBookmarks', params=params)
            
            # Handle response content
            if hasattr(response, 'content'):
                data = response.content
            else:
                print(f"Unexpected response type: {type(response)}")
                break
            
            batch = data.get('bookmarks', [])
            if not batch:
                print("No more bookmarks in batch.")
                break
                
            bookmarks.extend(batch)
            print(f"Fetched {len(batch)} bookmarks. Total: {len(bookmarks)}")
            
            new_cursor = data.get('cursor')
            if not new_cursor:
                print("No cursor returned. End of list.")
                break
            
            if new_cursor == cursor:
                print("Cursor did not change. Breaking loop.")
                break
                
            cursor = new_cursor
                
        except Exception as e:
            print(f"Error fetching bookmarks: {e}")
            import traceback
            traceback.print_exc()
            break
    
    if not bookmarks:
        print("No bookmarks found.")
        return

    print(f"Found {len(bookmarks)} bookmarks to process.")
    
    # --- Process Bookmarks ---
    for i, b in enumerate(bookmarks):
        print(f"\n--- Processing Bookmark {i+1} ---")
        
        # 1. Check for Orphaned Bookmarks (Post deleted)
        item = b.get('item')
        if not item or item.get('notFound'):
            print("Post not found (deleted). Deleting bookmark...")
            subject_uri = b.get('subject', {}).get('uri')
            if subject_uri:
                try:
                    # Call undocumented endpoint: app.bsky.bookmark.deleteBookmark
                    # CRITICAL: Must include Content-Type: application/json header
                    user_client.invoke_procedure(
                        'app.bsky.bookmark.deleteBookmark', 
                        data=ParamsModel({'uri': subject_uri}), 
                        headers={'Content-Type': 'application/json'}
                    )
                    print("Deleted bookmark for missing post.")
                except Exception as e:
                    print(f"Failed to delete bookmark: {e}")
            continue

        # 2. Extract Post Details
        uri = item.get('uri')
        print(f"URI: {uri}")
        
        author = item.get('author', {})
        author_handle = author.get('handle', '')
        print(f"Author: {author_handle}")
        
        record = item.get('record', {})
        text = record.get('text', '')
        
        # 3. Determine State/Bot from Author Handle
        state = None
        bot_key = None
        if 'vic' in author_handle.lower():
            state = 'VIC'
            bot_key = 'VIC'
        elif 'nsw' in author_handle.lower():
            state = 'NSW'
            bot_key = 'NSW'
        elif 'qld' in author_handle.lower():
            state = 'QLD'
            bot_key = 'QLD'
            
        if not state:
            print(f"Could not determine state from handle {author_handle}. Skipping.")
            continue
            
        # 4. Initialize Bot Poster (Lazy Loading)
        if bots[bot_key]['poster'] is None:
            print(f"Initializing poster for {state}...")
            try:
                bots[bot_key]['poster'] = BlueSkyPoster(bots[bot_key]['handle'], bots[bot_key]['password'])
                bots[bot_key]['poster'].authenticate()
            except Exception as e:
                print(f"Failed to login bot {state}: {e}")
                continue

        # 5. Identify Council
        # First try text match
        council = get_council_from_text(text, [c for c in all_councils if c['state'] == state])
        
        # 6. Extract Article URL
        article_url = None
        
        # Check embed first (most reliable for shared links)
        embed = item.get('embed')
        if embed and embed.get('$type') == 'app.bsky.embed.external#view':
             article_url = embed.get('external', {}).get('uri')
        
        # Fallback to facets (links in text)
        if not article_url and record.get('facets'):
            for facet in record['facets']:
                for feature in facet.get('features', []):
                    if feature.get('$type') == 'app.bsky.richtext.facet#link':
                        article_url = feature.get('uri')
                        break
                if article_url: break
        
        if not article_url:
            print("No article URL found. Skipping.")
            continue
            
        print(f"Article URL: {article_url}")

        # 7. Fallback Council Identification (URL Match)
        if not council:
            print("Could not identify council from text. Trying URL match...")
            try:
                u_domain = urlparse(article_url).netloc.replace('www.', '')
                
                for c in all_councils:
                    if c['state'] == state:
                        c_domain = urlparse(c['news_url']).netloc.replace('www.', '')
                        if c_domain in u_domain or u_domain in c_domain:
                            council = c
                            break
            except:
                pass
        
        if not council:
            print("Still could not identify council. Skipping.")
            continue
            
        print(f"Identified Council: {council['name']}")
        
        # 8. Re-scrape to get fresh data
        print("Re-scraping...")
        try:
            scraper = get_scraper(council)
            articles = scraper.scrape()
            
            found_article = None
            for art in articles:
                # Fuzzy match URL
                if art.url == article_url:
                    found_article = art
                    break
                # Try without query params
                if art.url.split('?')[0] == article_url.split('?')[0]:
                    found_article = art
                    break
            
            if found_article:
                print(f"Found fresh article data: {found_article.title}")
                
                # 9. Repost Corrected Article
                print("Reposting...")
                try:
                    bots[bot_key]['poster'].post_article(
                        council_name=council['name'],
                        title=found_article.title,
                        url=found_article.url,
                        date=found_article.date,
                        excerpt=found_article.excerpt
                    )
                    print("Successfully reposted.")
                    
                    # 10. Cleanup (Delete old post and bookmark)
                    print("Deleting old post...")
                    bots[bot_key]['poster'].client.delete_post(uri)
                    print("Deleted old post.")
                    
                    print("Deleting bookmark...")
                    user_client.invoke_procedure(
                        'app.bsky.bookmark.deleteBookmark', 
                        data=ParamsModel({'uri': uri}), 
                        headers={'Content-Type': 'application/json'}
                    )
                    print("Deleted bookmark.")
                
                except Exception as e:
                    print(f"Error during repost/delete: {e}")
            else:
                print("Could not find article in fresh scrape. Maybe it's too old?")
                
        except Exception as e:
            print(f"Error during scraping: {e}")

if __name__ == "__main__":
    fix_and_repost()

import os
import re
import time
from dotenv import load_dotenv
from atproto import Client
from core.poster import BlueSkyPoster

load_dotenv()

# Bots to check (add more if needed, but QLD was the main culprit)
TARGET_BOTS = [
    'roundupnewsbotqld.bsky.social',
    'roundupnewsbotnsw.bsky.social',
    'roundupnewsbotvic.bsky.social',
    'roundupnewsbotwa.bsky.social',
    'roundupnewsbotnt.bsky.social',
    'roundupnewsbottas.bsky.social',
    'roundupnewsbotsa.bsky.social'
]

def get_bot_credentials(handle):
    match = re.search(r'roundupnewsbot([a-z]+)', handle)
    if not match:
        return None, None
    state_code = match.group(1).upper()
    env_handle = os.getenv(f"BLUESKY_HANDLE_{state_code}")
    env_pass = os.getenv(f"BLUESKY_PASSWORD_{state_code}")
    return env_handle, env_pass

def is_malformed_tag_post(record):
    # record is a model object, usually
    text = getattr(record, 'text', '')
    if not text:
        return False
        
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return False
        
    last_line = lines[-1]
    
    # DEBUG:
    # print(f"CHECKING: {last_line}")
    
    # Check for the duplication signature: Non-hashed text that looks like tags
    # e.g. "LGNewsRoundup LGAQ QLDCouncils"
    # Use regex negative lookbehind to find "LGNewsRoundup" not preceded by "#"
    if re.search(r'(?<!#)LGNewsRoundup', last_line):
        return True
    
    return False

def clean_repost(client, poster, post):
    uri = post.uri
    record = post.record
    text = record.text
    
    # 1. Extract Details from the Post itself
    # Format:
    # Title
    # [Excerpt?]
    # [Date?]
    # Council Name
    # Tags...
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) < 2:
        print("    -> Content too short to parse. Skipping.")
        return False
        
    title = lines[0]
    
    # Council name is likely the line before the tags line
    # The tags line is the one with the junk.
    council_name = lines[-2] # Assuming last line is the junk tags
    
    # Verify title is not date-y (safety check)
    # The bugged posts had GOOD titles, so this should be fine.
    
    # Link
    link = None
    if hasattr(record, 'facets') and record.facets:
        for f in record.facets:
            for feat in f.features:
                if hasattr(feat, 'uri'):
                    link = feat.uri
                    break
            if link: break
            
    if not link:
        print("    -> No link found. Skipping.")
        return False

    print(f"    -> Parsing: Title='{title[:30]}...', Council='{council_name}'")
    
    # 2. Repost Cleanly
    # We pass hashtags=[] because poster generates the standard ones.
    # We trust 'council_name' is correct (it was correct in the screenshot).
    try:
        new_uri = poster.post_article(
            council_name=council_name,
            title=title,
            url=link,
            date=None,
            hashtags=[] 
        )
        if new_uri:
            print(f"    -> REPOST SUCCESS.")
            # 3. Delete Old
            client.delete_post(uri)
            print("    -> Deleted bad post.")
            time.sleep(2)
            return True
        else:
            print("    -> Repost failed (returned None).")
            return False
            
    except Exception as e:
        print(f"    -> Error during repost: {e}")
        return False

def main():
    print("Starting Tag Cleanup...")
    
    for handle in TARGET_BOTS:
        user, pwd = get_bot_credentials(handle)
        if not user:
            continue
            
        print(f"\nScanning {handle}...")
        try:
            client = Client()
            client.login(user, pwd)
            poster = BlueSkyPoster(user, pwd)
            
            # Fetch Author Feed (Timeline)
            # app.bsky.feed.getAuthorFeed
            data = client.app.bsky.feed.get_author_feed({'actor': user, 'limit': 100})
            feed = data.feed
            
            print(f"  Found {len(feed)} items in feed.")
            
            for i, item in enumerate(feed):
                post = item.post
                # DEBUG REMOVED
                
                if is_malformed_tag_post(post.record):
                    print(f"  [BAD TAGS]: {post.record.text[:40]}...")
                    clean_repost(client, poster, post)
                else:
                    # print(f"  [OK]: {post.record.text[:20]}...")
                    pass
                    
        except Exception as e:
            print(f"  Error processing {handle}: {e}")

if __name__ == "__main__":
    main()

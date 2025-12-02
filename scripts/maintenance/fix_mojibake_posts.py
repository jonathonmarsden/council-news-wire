import os
import sys
import re
import time
from dotenv import load_dotenv
from atproto import Client, client_utils

# Load environment variables
load_dotenv()

def clean_text(text):
    """Clean and normalize text content."""
    if not isinstance(text, str):
        return text
        
    # Fix common mojibake (UTF-8 bytes interpreted as Windows-1252/Latin-1)
    replacements = {
        'â': "'",
        'â\x80\x99': "'",
        'â': "-",
        'â\x80\x93': "-",
        'â': "-",
        'â\x80\x94': "-",
        'â': '"',
        'â\x80\x9c': '"',
        'â': '"',
        'â\x80\x9d': '"',
        'â¦': '...',
        'â\x80\xa6': '...',
        'Â': '',  # Non-breaking space artifact
        '\xa0': ' ', # Non-breaking space
        '\u00a0': ' ', # Non-breaking space unicode
    }
    
    for bad, good in replacements.items():
        text = text.replace(bad, good)
        
    # Normalize whitespace line by line to preserve structure
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Normalize whitespace within the line
        cleaned_line = re.sub(r'\s+', ' ', line).strip()
        cleaned_lines.append(cleaned_line)
            
    return '\n'.join(cleaned_lines)

def get_mojibake_chars():
    return [
        'â', 'â\x80\x99', 'â', 'â\x80\x93', 'â', 'â\x80\x94',
        'â', 'â\x80\x9c', 'â', 'â\x80\x9d', 'â¦', 'â\x80\xa6', 'Â'
    ]

def has_mojibake(text):
    for char in get_mojibake_chars():
        if char in text:
            return True
    return False

def main():
    handle = os.getenv('BLUESKY_HANDLE')
    password = os.getenv('BLUESKY_PASSWORD')
    
    if not handle or not password:
        print("Error: BLUESKY_HANDLE and BLUESKY_PASSWORD must be set.")
        return

    print(f"Connecting to BlueSky as {handle}...")
    client = Client()
    try:
        client.login(handle, password)
    except Exception as e:
        print(f"Failed to login: {e}")
        return

    print("Fetching recent posts...")
    
    cursor = None
    all_posts = []
    
    while True:
        feed = client.get_author_feed(actor=client.me.did, limit=100, cursor=cursor)
        all_posts.extend(feed.feed)
        
        if not feed.cursor:
            break
            
        cursor = feed.cursor
        print(f"Fetched {len(all_posts)} posts so far...")
        
        # Safety break
        if len(all_posts) > 500:
            break
    
    print(f"Total posts fetched: {len(all_posts)}")
    
    fixed_count = 0
    
    for feed_view in all_posts:
        post = feed_view.post
        record = post.record
        text = record.text
        
        # Debug: Check for Paynesville
        if 'Paynesville' in text:
            print(f"\nDEBUG: Found Paynesville post: {text}")
            print(f"Mojibake check: {has_mojibake(text)}")
        
        if has_mojibake(text):
            print(f"\nFound mojibake in post: {post.uri}")
            print(f"Original text:\n{text}")
            
            # Extract URL from facets
            url = None
            if hasattr(record, 'facets') and record.facets:
                # Assume the first facet is the main link (Title)
                for facet in record.facets:
                    for feature in facet.features:
                        if hasattr(feature, 'uri'):
                            url = feature.uri
                            break
                    if url:
                        break
            
            if not url:
                print("⚠️  No URL found in facets. Skipping.")
                continue
                
            # Clean the text
            cleaned_text = clean_text(text)
            print(f"Cleaned text:\n{cleaned_text}")
            
            if cleaned_text == text:
                print("⚠️  Text didn't change after cleaning. Skipping.")
                continue
                
            # Reconstruct the post
            # We assume the first line is the title and should be linked
            lines = cleaned_text.split('\n')
            title = lines[0]
            body = '\n'.join(lines[1:])
            
            print(f"Title (Linked): {title}")
            print(f"URL: {url}")
            print(f"Body: {body}")
            
            if '--force' in sys.argv:
                confirm = 'y'
            else:
                confirm = input("Delete and repost? (y/n): ")
            
            if confirm.lower() == 'y':
                try:
                    # Delete original post
                    print("Deleting original post...")
                    client.delete_post(post.uri)
                    
                    # Create new post
                    print("Creating new post...")
                    tb = client_utils.TextBuilder()
                    tb.link(title, url)
                    if body:
                        tb.text(f"\n{body}")
                    
                    client.send_post(tb)
                    print("✅ Fixed successfully!")
                    fixed_count += 1
                    
                    # Sleep briefly to avoid rate limits
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"❌ Failed to fix post: {e}")
            else:
                print("Skipping.")
    
    print(f"\nFinished. Fixed {fixed_count} posts.")

if __name__ == "__main__":
    main()

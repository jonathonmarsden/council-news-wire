import os
import sys
from atproto import Client

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def inspect_saved_posts():
    handle = os.environ.get('BLUESKY_HANDLE_DEBUG', "jonathonmarsden.com")
    password = os.environ.get('BLUESKY_PASSWORD_DEBUG', "***REMOVED***")
    
    print(f"\n--- Checking {handle} ---")
    
    try:
        client = Client()
        client.login(handle, password)
        print("Authenticated.")
        
        response = client.app.bsky.bookmark.get_bookmarks()
        bookmarks = response.bookmarks
        
        if not bookmarks:
            print("No saved posts found.")
        else:
            print(f"Found {len(bookmarks)} saved posts:")
            for i, bookmark in enumerate(bookmarks):
                print(f"\n--- Bookmark {i+1} ---")
                uri = bookmark.subject.uri
                print(f"URI: {uri}")
                
                # The bookmark view contains the 'item' which is the post view
                item = bookmark.item
                
                if hasattr(item, 'record'):
                    record = item.record
                    print(f"Text: {record.text}")
                    if hasattr(record, 'facets') and record.facets:
                        print("Facets:")
                        for facet in record.facets:
                            print(f"  - {facet}")
                    if hasattr(record, 'embed') and record.embed:
                        print(f"Embed: {record.embed}")
                
                # Get author to know which bot posted it
                if hasattr(item, 'author'):
                    print(f"Author: {item.author.handle}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_saved_posts()

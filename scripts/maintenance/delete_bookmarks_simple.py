import os
import sys
from atproto import Client, models

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def delete_bookmarks_simple():
    handle = os.environ.get('BLUESKY_HANDLE_DEBUG', "jonathonmarsden.com")
    password = os.environ.get('BLUESKY_PASSWORD_DEBUG', "***REMOVED***")
    
    print(f"\n--- Authenticating as {handle} ---")
    client = Client()
    client.login(handle, password)
    print("Authenticated.")
    
    # Get Bookmarks
    response = client.app.bsky.bookmark.get_bookmarks()
    bookmarks = response.bookmarks
    
    if not bookmarks:
        print("No bookmarks found.")
        return

    print(f"Found {len(bookmarks)} bookmarks to delete.")
    
    deleted_count = 0
    for bookmark in bookmarks:
        post_uri = bookmark.subject.uri
        print(f"Deleting bookmark for post {post_uri}")
        try:
            # The high-level method delete_bookmark likely takes the post URI
            # and handles the lookup/deletion internally.
            # It requires a Data object
            data = models.AppBskyBookmarkDeleteBookmark.Data(uri=post_uri)
            client.app.bsky.bookmark.delete_bookmark(data=data)
            deleted_count += 1
            print("Deleted.")
        except Exception as e:
            print(f"Error deleting bookmark: {e}")
            
    print(f"Deleted {deleted_count} bookmarks.")

if __name__ == "__main__":
    delete_bookmarks_simple()

import os
import sys
from dotenv import load_dotenv
from atproto import Client

# Add project root to path to allow imports if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_saved_posts():
    load_dotenv()
    
    accounts = [
        {'state': 'VIC', 'handle_env': 'BLUESKY_HANDLE_VIC', 'password_env': 'BLUESKY_PASSWORD_VIC'},
        {'state': 'NSW', 'handle_env': 'BLUESKY_HANDLE_NSW', 'password_env': 'BLUESKY_PASSWORD_NSW'},
        {'state': 'QLD', 'handle_env': 'BLUESKY_HANDLE_QLD', 'password_env': 'BLUESKY_PASSWORD_QLD'},
    ]
    
    for account in accounts:
        state = account['state']
        handle = os.environ.get(account['handle_env'])
        password = os.environ.get(account['password_env'])
        
        print(f"\n--- Checking {state} ({handle}) ---")
        
        if not handle or not password:
            print(f"Credentials not found for {state}")
            continue
            
        try:
            client = Client()
            client.login(handle, password)
            print("Authenticated.")
            
            # Fetch bookmarks
            # Note: The method might vary slightly depending on the SDK version
            # Trying app.bsky.bookmark.get_bookmarks if available, or actor.get_preferences
            
            # In some versions, bookmarks are private and might not be exposed via a simple get_bookmarks 
            # if it's not in the main lexicon yet, but the grep showed it exists.
            
            try:
                # Attempt to use the method found in grep
                # get_bookmarks does not take 'repo' argument, it implies self
                response = client.app.bsky.bookmark.get_bookmarks()
                bookmarks = response.bookmarks
                
                if not bookmarks:
                    print("No saved posts found.")
                else:
                    print(f"Found {len(bookmarks)} saved posts:")
                    for bookmark in bookmarks:
                        # bookmark is a BookmarkView
                        uri = bookmark.subject.uri
                        print(f"\n- URI: {uri}")
                        
                        # Try to print post content if available
                        if hasattr(bookmark.item, 'record') and hasattr(bookmark.item.record, 'text'):
                            print(f"  Text: {bookmark.item.record.text[:100]}...")
                        elif hasattr(bookmark.item, 'uri'):
                             print(f"  Item URI: {bookmark.item.uri}")

                        
            except AttributeError:
                print("client.app.bsky.bookmark.get_bookmarks not found. Trying alternative...")
                # Fallback or debugging
                print(dir(client.app.bsky))
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check_saved_posts()

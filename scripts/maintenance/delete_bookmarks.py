import os
import sys
from atproto import Client, models

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def delete_bookmarks():
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
    
    # Fetch all bookmark records to map URI to RKEY
    print("Fetching bookmark records...")
    # We need to use the correct params model
    params = models.ComAtprotoRepoListRecords.Params(
        collection='app.bsky.bookmark',
        repo=client.me.did,
        limit=100
    )
    records_response = client.com.atproto.repo.list_records(params=params)
    
    # Map post URI to bookmark rkey
    post_uri_to_rkey = {}
    print(f"Found {len(records_response.records)} records.")
    for record in records_response.records:
        # record.value is the record data (Bookmark)
        # record.value.subject is the StrongRef to the post
        # print(f"Record: {record.uri}, Subject: {record.value.subject.uri}")
        post_uri_to_rkey[record.value.subject.uri] = record.uri.split('/')[-1]
        
    deleted_count = 0
    for bookmark in bookmarks:
        post_uri = bookmark.subject.uri
        rkey = post_uri_to_rkey.get(post_uri)
        
        if rkey:
            print(f"Deleting bookmark for post {post_uri} (rkey: {rkey})")
            data = models.ComAtprotoRepoDeleteRecord.Data(
                collection='app.bsky.bookmark',
                repo=client.me.did,
                rkey=rkey
            )
            client.com.atproto.repo.delete_record(data=data)
            deleted_count += 1
        else:
            print(f"Could not find rkey for bookmark {post_uri}")
            
    print(f"Deleted {deleted_count} bookmarks.")

if __name__ == "__main__":
    delete_bookmarks()

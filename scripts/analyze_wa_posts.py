import os
import sys
from atproto import Client

# Add project root to path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

def analyze_posts():
    handle = os.getenv("BLUESKY_HANDLE_WA")
    password = os.getenv("BLUESKY_PASSWORD_WA")

    if not handle or not password:
        print("Error: WA BlueSky credentials not found in environment.")
        return

    client = Client()
    try:
        client.login(handle, password)
        print(f"Authenticated as {handle}")
    except Exception as e:
        print(f"Authentication failed: {e}")
        return

    post_urls = [
        "https://bsky.app/profile/roundupnewsbotwa.bsky.social/post/3m76t4zr6jy2m",
        "https://bsky.app/profile/roundupnewsbotwa.bsky.social/post/3m76t53u26n27",
        "https://bsky.app/profile/roundupnewsbotwa.bsky.social/post/3m76tfzm4jv2j",
        "https://bsky.app/profile/roundupnewsbotwa.bsky.social/post/3m76tg3osd627",
        "https://bsky.app/profile/roundupnewsbotwa.bsky.social/post/3m76txt4wtj2r",
        "https://bsky.app/profile/roundupnewsbotwa.bsky.social/post/3m76ukjnv7b2f",
        "https://bsky.app/profile/roundupnewsbotwa.bsky.social/post/3m76uskihnj2v",
        "https://bsky.app/profile/roundupnewsbotwa.bsky.social/post/3m76txv7vl42j"
    ]

    did = client.me.did
    
    print("\n--- Analyzing Posts ---\n")

    for url in post_urls:
        rkey = url.split('/')[-1]
        uri = f"at://{did}/app.bsky.feed.post/{rkey}"
        
        try:
            response = client.get_posts(uris=[uri])
            if response.posts:
                post = response.posts[0]
                record = post.record
                print(f"Rkey: {rkey}")
                print(f"Text: {record.text}")
                print(f"Date: {record.created_at}")
                print("-" * 40)
            else:
                print(f"Post {rkey} not found (maybe already deleted).")
                
        except Exception as e:
            print(f"Error fetching post {rkey}: {e}")

if __name__ == "__main__":
    analyze_posts()

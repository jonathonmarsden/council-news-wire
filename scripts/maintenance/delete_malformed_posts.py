import os
import sys
from dotenv import load_dotenv
from atproto import Client, models

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def delete_malformed_posts():
    load_dotenv()
    
    # Map DIDs to Bot Config
    bots = {
        'did:plc:ipvwoaox23hbogsq6f6bjkjh': {
            'state': 'NSW',
            'handle_env': 'BLUESKY_HANDLE_NSW',
            'password_env': 'BLUESKY_PASSWORD_NSW',
            'client': None
        },
        'did:plc:7x2efegtjd3jkyizpl7crntu': {
            'state': 'QLD',
            'handle_env': 'BLUESKY_HANDLE_QLD',
            'password_env': 'BLUESKY_PASSWORD_QLD',
            'client': None
        },
        'did:plc:j7do2kxrqkstt3wxng3nkffb': {
            'state': 'VIC',
            'handle_env': 'BLUESKY_HANDLE_VIC',
            'password_env': 'BLUESKY_PASSWORD_VIC',
            'client': None
        }
    }
    
    posts_to_delete = [
        "at://did:plc:ipvwoaox23hbogsq6f6bjkjh/app.bsky.feed.post/3m6x3tt2udc2a",
        "at://did:plc:ipvwoaox23hbogsq6f6bjkjh/app.bsky.feed.post/3m6wz2kjbx62s",
        "at://did:plc:ipvwoaox23hbogsq6f6bjkjh/app.bsky.feed.post/3m6wzdbhihe2x",
        "at://did:plc:ipvwoaox23hbogsq6f6bjkjh/app.bsky.feed.post/3m6x3bmncpb2z",
        "at://did:plc:ipvwoaox23hbogsq6f6bjkjh/app.bsky.feed.post/3m6x3l5mldy24",
        "at://did:plc:ipvwoaox23hbogsq6f6bjkjh/app.bsky.feed.post/3m6wazqnyx72m",
        "at://did:plc:ipvwoaox23hbogsq6f6bjkjh/app.bsky.feed.post/3m6wbch5hju2c",
        "at://did:plc:ipvwoaox23hbogsq6f6bjkjh/app.bsky.feed.post/3m6vp5nhhs426",
        "at://did:plc:ipvwoaox23hbogsq6f6bjkjh/app.bsky.feed.post/3m6vouw4rbe24",
        "at://did:plc:ipvwoaox23hbogsq6f6bjkjh/app.bsky.feed.post/3m6vomxle7626",
        "at://did:plc:7x2efegtjd3jkyizpl7crntu/app.bsky.feed.post/3m6voa4c4422f",
        "at://did:plc:7x2efegtjd3jkyizpl7crntu/app.bsky.feed.post/3m6voa27je22r",
        "at://did:plc:7x2efegtjd3jkyizpl7crntu/app.bsky.feed.post/3m6vmw25ubl2c",
        "at://did:plc:7x2efegtjd3jkyizpl7crntu/app.bsky.feed.post/3m6vn6rxzzn2w",
        "at://did:plc:7x2efegtjd3jkyizpl7crntu/app.bsky.feed.post/3m6vnhl4zrn2c",
        "at://did:plc:7x2efegtjd3jkyizpl7crntu/app.bsky.feed.post/3m6vnrbjkw22u",
        "at://did:plc:7x2efegtjd3jkyizpl7crntu/app.bsky.feed.post/3m6vnzzhyyc2e",
        "at://did:plc:j7do2kxrqkstt3wxng3nkffb/app.bsky.feed.post/3m6q2jareez2y",
        "at://did:plc:j7do2kxrqkstt3wxng3nkffb/app.bsky.feed.post/3m6ojcu6fst22"
    ]
    
    print(f"Found {len(posts_to_delete)} posts to delete.")
    
    for uri in posts_to_delete:
        # Parse URI
        # at://<did>/<collection>/<rkey>
        parts = uri.replace("at://", "").split('/')
        did = parts[0]
        collection = parts[1]
        rkey = parts[2]
        
        if did not in bots:
            print(f"Unknown bot DID: {did}")
            continue
            
        bot_config = bots[did]
        
        # Initialize client if needed
        if not bot_config['client']:
            print(f"Authenticating {bot_config['state']} bot...")
            handle = os.environ.get(bot_config['handle_env'])
            password = os.environ.get(bot_config['password_env'])
            
            if not handle or not password:
                print(f"Missing credentials for {bot_config['state']}")
                continue
                
            try:
                client = Client()
                client.login(handle, password)
                bot_config['client'] = client
                print(f"Authenticated as {handle}")
            except Exception as e:
                print(f"Failed to authenticate: {e}")
                continue
        
        client = bot_config['client']
        if not client:
            continue
            
        print(f"Deleting post {rkey} from {bot_config['state']}...")
        try:
            client.delete_post(post_uri=uri)
            print("Deleted.")
        except Exception as e:
            print(f"Error deleting post: {e}")

if __name__ == "__main__":
    delete_malformed_posts()

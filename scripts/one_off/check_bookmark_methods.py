from atproto import Client
import os

handle = os.environ.get('BLUESKY_HANDLE_DEBUG', "jonathonmarsden.com")
password = os.environ.get('BLUESKY_PASSWORD_DEBUG', "***REMOVED***")
client = Client()
client.login(handle, password)

print(dir(client.app.bsky.bookmark))

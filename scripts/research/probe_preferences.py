import os
import sys
import json
from dotenv import load_dotenv
from atproto import Client

# Add project root to path
root_dir = os.path.join(os.path.dirname(__file__), '../../')
sys.path.append(root_dir)

load_dotenv(os.path.join(root_dir, '.env'))

BSKY_HANDLE = os.getenv("BLUESKY_HANDLE_ADMIN")
BSKY_PASSWORD = os.getenv("BLUESKY_PASSWORD_ADMIN")

def probe_preferences():
    print(f"Logging in as {BSKY_HANDLE}...")
    client = Client()
    client.login(BSKY_HANDLE, BSKY_PASSWORD)

    print("\n--- Probing app.bsky.actor.getPreferences ---")
    try:
        preferences = client.app.bsky.actor.get_preferences()
        print("Success!")
        # preferences is likely a specific response object. 
        # We want to see what's inside.
        print(preferences)
        
        # If it's a list or object, let's look for known types
        if hasattr(preferences, 'preferences'):
            for pref in preferences.preferences:
                print(f"Type: {type(pref)}")
                print(pref)
                # Check for "saved" or "bookmark" in the string representation or attributes
                if "saved" in str(pref).lower() or "bookmark" in str(pref).lower():
                    print("!!! FOUND POTENTIAL MATCH !!!")
                    print(pref)

    except Exception as e:
        print(f"Failed get_preferences: {e}")

if __name__ == "__main__":
    probe_preferences()

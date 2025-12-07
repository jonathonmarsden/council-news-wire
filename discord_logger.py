import requests
import json
import os
from datetime import datetime

# You can hardcode this or load from env
DISCORD_WEBHOOK_URL = "***REMOVED***"

def log_post_success(council_name, title, url, post_uri, date=None, hashtags=None):
    """Logs a successful post to Discord with a replica of the Bluesky post."""
    
    # Recreate the Bluesky post content
    post_lines = [title]
    if date:
        post_lines.append(date.strftime('%d %B %Y') if hasattr(date, 'strftime') else str(date))
    post_lines.append(council_name)
    if hashtags:
        post_lines.append(' '.join(hashtags))
    
    post_replica = '\n'.join(post_lines)
    
    # Build Bluesky URL
    bsky_url = f"https://bsky.app/profile/{post_uri.split('/')[2]}/post/{post_uri.split('/')[-1]}"
    
    # Create an 'Embed' for prettier formatting
    embed = {
        "title": f"✅ New Post: {council_name}",
        "color": 3066993, # Green
        "fields": [
            {
                "name": "Post Content",
                "value": f"```\n{post_replica}\n```",
                "inline": False
            },
            {
                "name": "Original Article",
                "value": url,
                "inline": False
            },
            {
                "name": "Bluesky Post",
                "value": bsky_url,
                "inline": False
            }
        ],
        "timestamp": datetime.now().isoformat()
    }
    
    _send_discord_embed(embed)

def log_error(council_name, error_message, context=""):
    """Logs an error to Discord."""
    embed = {
        "title": f"❌ Error: {council_name}",
        "description": error_message,
        "color": 15158332, # Red
        "fields": [
            {
                "name": "Context",
                "value": context,
                "inline": False
            }
        ],
        "timestamp": datetime.now().isoformat()
    }
    _send_discord_embed(embed)

def _send_discord_embed(embed_dict):
    if not DISCORD_WEBHOOK_URL:
        return
        
    data = {
        "embeds": [embed_dict],
        "username": "Roundup News Bot Logger"
    }
    
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data)
    except Exception as e:
        print(f"Failed to log to Discord: {e}")

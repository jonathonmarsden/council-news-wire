import requests
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional

# Load hooks from Env, fallback to default if not set (for backward compatibility)
DISCORD_WEBHOOK_URL_DEFAULT = "***REMOVED***"

# Configurable hooks for different channels
WEBHOOK_ALERTS = os.environ.get("DISCORD_WEBHOOK_ALERTS", DISCORD_WEBHOOK_URL_DEFAULT)
WEBHOOK_LOGS = os.environ.get("DISCORD_WEBHOOK_LOGS", DISCORD_WEBHOOK_URL_DEFAULT)
WEBHOOK_FEED = os.environ.get("DISCORD_WEBHOOK_FEED", DISCORD_WEBHOOK_URL_DEFAULT)

class RunAccumulator:
    """Accumulates stats during a scraper run to avoid chatty logs."""
    def __init__(self):
        self.councils_scraped = 0
        self.articles_found = 0
        self.articles_posted = 0
        self.errors: List[Dict] = []
        self.start_time = datetime.now(timezone.utc)
        self.silent_failures: List[str] = []

    def log_success(self, council_name, found, posted):
        self.councils_scraped += 1
        self.articles_found += found
        self.articles_posted += posted

    def log_error(self, council_name, error_msg):
        self.errors.append({
            "council": council_name,
            "error": str(error_msg)
        })

    def log_silent_failure(self, council_id):
        self.silent_failures.append(council_id)

    def send_summary(self, state_code: str):
        """Sends a summarized report of the run."""
        duration = datetime.now(timezone.utc) - self.start_time
        duration_str = str(duration).split('.')[0] # Remove microseconds

        # Determine color (Green if clean, Red if errors)
        color = 3066993 if not self.errors else 15158332
        
        status_emoji = "🟢"
        if self.errors:
            status_emoji = "🟠" 
        if len(self.errors) > 5:
            status_emoji = "🔴"

        description = (
            f"**State**: {state_code.upper()}\n"
            f"**Time**: {duration_str}\n"
            f"**Councils**: {self.councils_scraped}\n"
            f"**Articles Found**: {self.articles_found}\n"
            f"**New Posted**: {self.articles_posted}"
        )

        fields = []
        
        # Add Silent Failures if any (Limit to 10)
        if self.silent_failures:
            failures_list = ", ".join(self.silent_failures[:15])
            if len(self.silent_failures) > 15:
                failures_list += f" (+{len(self.silent_failures)-15} more)"
            
            fields.append({
                "name": f"⚠️ Silent Failures ({len(self.silent_failures)})",
                "value": f"`{failures_list}`",
                "inline": False
            })

        # Add Errors if any (Limit to 5 detailed)
        if self.errors:
            error_details = []
            for err in self.errors[:5]:
                error_details.append(f"**{err['council']}**: {err['error'][:100]}")
            
            if len(self.errors) > 5:
                error_details.append(f"...and {len(self.errors)-5} more errors.")
                
            fields.append({
                "name": f"❌ Scraper Errors ({len(self.errors)})",
                "value": "\n".join(error_details),
                "inline": False
            })

        embed = {
            "title": f"{status_emoji} Scraper Run Summary: {state_code.upper()}",
            "description": description,
            "color": color,
            "fields": fields,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Send to Logs channel
        _send_webhook(WEBHOOK_LOGS, embed)

        # If there are critical errors, ALSO send to Alerts channel
        if len(self.errors) > 2 or any("Timeout" in e['error'] for e in self.errors):
             _send_webhook(WEBHOOK_ALERTS, embed)

# Global accumulator instance
current_run = RunAccumulator()

def reset_accumulator():
    global current_run
    current_run = RunAccumulator()

def log_post_success(council_name, title, url, post_uri, date=None, hashtags=None):
    """Logs a successful post to Discord (The public feed)."""
    
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
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    _send_webhook(WEBHOOK_FEED, embed)

def log_error(council_name, error_message, context=""):
    """
    Logs an error.
    - Adds to accumulator for summary.
    - If critical, sends immediate alert.
    """
    # Simply add to accumulator, summary will handle reporting
    current_run.log_error(council_name, error_message)
    
    # OPTIONAL: Keep urgent immediate logging for fatal system things?
    # For now, we trust the summary at the end of the run.

def log_silent_failure(council_id):
    current_run.log_silent_failure(council_id)

def log_generic_report(title, description, color=3447003):
    """Logs a generic report/message to Discord (e.g. Quiet Councils)."""
    embed = {
        "title": title,
        "description": description[:4000],
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    _send_webhook(WEBHOOK_LOGS, embed)

def _send_webhook(url, embed_dict):
    if not url:
        print("Discord webhook URL not configured; skipping log")
        return

    data = {
        "embeds": [embed_dict],
        "username": "Roundup News Bot Logger"
    }

    # Attempt with retries to handle transient network / rate-limit issues
    max_attempts = 3
    backoff = 1
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, json=data, timeout=10)
        except Exception as e:
            print(f"Attempt {attempt}: Failed to send Discord webhook (exception): {e}")
            resp = None

        if resp is None:
            # network error, retry
            if attempt < max_attempts:
                time_sleep = backoff
                backoff *= 2
                try:
                    from time import sleep
                    sleep(time_sleep)
                except Exception:
                    pass
                continue
            else:
                print("Discord webhook failed after retries (network error)")
                return

        # Check HTTP response
        if resp.status_code in (200, 204):
            # success
            return
        elif resp.status_code == 429:
            # Rate limited — try again after delay if available
            retry_after = resp.headers.get("Retry-After")
            print(f"Attempt {attempt}: Discord webhook rate limited, Retry-After={retry_after}")
            if attempt < max_attempts:
                try:
                    wait = int(retry_after) if retry_after and retry_after.isdigit() else backoff
                except Exception:
                    wait = backoff
                backoff *= 2
                try:
                    from time import sleep
                    sleep(wait)
                except Exception:
                    pass
                continue
            else:
                print("Discord webhook failed after retries (rate limited)")
                print("Response:", resp.status_code, resp.text[:1000])
                return
        else:
            # Non-retryable HTTP error
            print(f"Discord webhook returned HTTP {resp.status_code}: {resp.text[:1000]}")
            return


import requests
import feedparser

def check_feed(url):
    print(f"Checking {url}...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15'
        }
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            print(f"Feed Title: {feed.feed.get('title', 'Unknown')}")
            print(f"Entries: {len(feed.entries)}")
            if len(feed.entries) > 0:
                print(f"First Entry: {feed.entries[0].title}")
                print(f"First Entry Link: {feed.entries[0].link}")
        else:
            print("Failed to fetch feed")
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 20)

check_feed("https://lockhart.nsw.gov.au/feed/")
check_feed("https://www.bogan.nsw.gov.au/news?format=feed&type=rss")

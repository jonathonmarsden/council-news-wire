import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from curl_cffi import requests

def check_lockhart():
    print("\n--- Checking Lockhart RSS ---")
    rss_url = "https://lockhart.nsw.gov.au/feed/"
    try:
        response = requests.get(rss_url, impersonate="chrome110", timeout=30, verify=False)
        print(f"Lockhart RSS status: {response.status_code}")
        print(f"Lockhart RSS len: {len(response.text)}")
        print("--- RSS CONTENT ---")
        print(response.text[:2000]) # Print first 2000 chars
    except Exception as e:
        print(f"Lockhart RSS failed: {e}")

    print("\n--- Checking Lockhart HTML with Safari ---")
    html_url = "https://lockhart.nsw.gov.au/council/latest-news/"
    try:
        response = requests.get(html_url, impersonate="safari15_3", timeout=30, verify=False)
        print(f"Lockhart HTML (Safari) status: {response.status_code}")
        print(f"Lockhart HTML (Safari) len: {len(response.text)}")
        if len(response.text) > 1000:
             # Check for common news classes
             if "elementor-post" in response.text:
                 print("Found 'elementor-post' class!")
             else:
                 print("Did NOT find 'elementor-post' class.")
    except Exception as e:
        print(f"Lockhart HTML failed: {e}")

def check_bogan_feed():
    print("\n--- Checking Bogan HTML Check ---")
    bogan_url = "https://www.bogan.nsw.gov.au/news"
    try:
        response = requests.get(bogan_url, impersonate="safari15_3", timeout=60, verify=False)
        print(f"Bogan Status: {response.status_code}")
        print(f"Bogan Len: {len(response.text)}")
        if response.status_code == 200:
            with open("bogan_debug.html", "w") as f:
                f.write(response.text)
            print("Dumped Bogan HTML to bogan_debug.html")
    except Exception as e:
        print(f"Bogan HTML failed: {e}")

if __name__ == "__main__":
    check_lockhart()
    check_bogan_feed()

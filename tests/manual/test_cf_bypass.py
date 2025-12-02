
import subprocess
import sys

def fetch_with_curl(url, mobile_mode=False):
    print(f"Fetching {url} (Mobile: {mobile_mode})...")
    cmd = [
        'curl', '-s', '-L',
        '--connect-timeout', '30',
        '--max-time', '60'
    ]
    
    if mobile_mode:
        cmd.extend([
            '-A', 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            '--http1.1'
        ])
    else:
        cmd.extend([
            '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ])
        
    cmd.append(url)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90
        )
        if result.returncode == 0:
            print(f"Success! Length: {len(result.stdout)}")
            if "Just a moment..." in result.stdout:
                print("Result: BLOCKED (Cloudflare Challenge)")
            else:
                print("Result: SUCCESS (Content retrieved)")
                print(result.stdout[:500])
        else:
            print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"Exception: {e}")

urls = [
    "https://www.circularhead.tas.gov.au/news",
    "https://www.derwentvalley.tas.gov.au/home/latest-news",
    "https://www.kentish.tas.gov.au/council/latest-news"
]

print("--- Standard Mode ---")
for url in urls:
    fetch_with_curl(url, mobile_mode=False)

print("\n--- Mobile Mode ---")
for url in urls:
    fetch_with_curl(url, mobile_mode=True)

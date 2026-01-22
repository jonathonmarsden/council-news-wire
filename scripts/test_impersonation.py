from curl_cffi import requests

URL = "https://www.lakemac.com.au/For-residents/History-and-heritage/News"

print("Testing Impersonations...")

targets = ["chrome110", "chrome120", "safari15_3", "safari17_0"]

for t in targets:
    try:
        resp = requests.get(URL, impersonate=t, timeout=10)
        print(f"{t}: {resp.status_code} (Len: {len(resp.text)})")
    except Exception as e:
        print(f"{t}: Error {e}")

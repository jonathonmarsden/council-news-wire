from curl_cffi import requests

urls = [
    "https://www.carpentaria.qld.gov.au/Council/Public-Notices",
    "https://www.carpentaria.qld.gov.au/Council/Latest-News",
    "https://www.carpentaria.qld.gov.au/Council/News-Media",
    "https://www.carpentaria.qld.gov.au/news"
]

for url in urls:
    try:
        response = requests.get(url, impersonate="chrome120", timeout=10)
        print(f"{url}: {response.status_code}")
    except Exception as e:
        print(f"{url}: Error {e}")

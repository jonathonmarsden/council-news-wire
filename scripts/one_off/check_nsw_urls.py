import requests

candidates = {
    "Bourke Shire Council": "https://bourke.nsw.gov.au/council/news-media/",
    "Coonamble Shire Council": "https://www.coonambleshire.nsw.gov.au/Council/News-and-Media",
    "Kyogle Council": "https://www.kyogle.nsw.gov.au/Council/News-and-Media",
    "Moree Plains Shire Council": "https://www.mpsc.nsw.gov.au/Council/News-Media",
    "Muswellbrook Shire Council": "https://www.muswellbrook.nsw.gov.au/Council/News-and-Media",
    "Narromine Shire Council": "https://www.narromine.nsw.gov.au/news",
    "Tenterfield Shire Council": "https://www.tenterfield.nsw.gov.au/Council/News-Media",
    "Warren Shire Council": "https://www.warren.nsw.gov.au/Council/News-and-Media"
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
}

print("Checking candidate URLs...")
for name, url in candidates.items():
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"{name}: {url} -> {response.status_code}")
    except Exception as e:
        print(f"{name}: {url} -> Error: {e}")

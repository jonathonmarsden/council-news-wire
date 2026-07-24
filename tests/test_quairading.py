from curl_cffi import requests
import requests as standard_requests
import pytest

pytestmark = pytest.mark.integration

def test_quairading_rss():
    url = "https://www.quairading.wa.gov.au/feed/"
    try:
        # Test 1: Curl UA
        print("--- Testing Curl UA (Standard Requests) ---")
        curl_headers = {'User-Agent': 'curl/7.64.1'}
        r = standard_requests.get(url, headers=curl_headers, timeout=30) 
        print(f"Status: {r.status_code}")
        
        # Test 2: Chrome UA
        print("--- Testing Chrome UA (Standard Requests) ---")
        chrome_headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        r = standard_requests.get(url, headers=chrome_headers, timeout=30) 
        print(f"Status: {r.status_code}")
        
        # Test 3: No UA (Default requests UA)
        print("--- Testing No UA (Standard Requests) ---")
        r = standard_requests.get(url, timeout=30) 
        print(f"Status: {r.status_code}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_quairading_rss()

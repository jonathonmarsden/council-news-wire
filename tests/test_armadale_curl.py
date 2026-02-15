from curl_cffi import requests

def test_armadale():
    url = "https://my.armadale.wa.gov.au/service/news-and-media-releases"
    print(f"Fetching {url}...")
    try:
        response = requests.get(url, impersonate="chrome120", timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Length: {len(response.text)}")
        if "RICKI-LEE" in response.text:
            print("Found 'RICKI-LEE' in response!")
        else:
            print("Did NOT find 'RICKI-LEE'.")
        
        # Check for JSON blobs
        if "self.__next_f.push" in response.text:
            print("Found Next.js hydration scripts.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_armadale()

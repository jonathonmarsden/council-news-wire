import requests

def check_redirect(url):
    print(f"Checking URL: {url[:100]}...")
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        print(f"Final URL: {response.url}")
        print(f"History: {[r.url for r in response.history]}")
        return response.url
    except Exception as e:
        print(f"Error: {e}")

url = "https://lgasa-search.squiz.cloud/s/redirect?collection=barunga-west-council-news-push&url=https%3A%2F%2Flgasa-web.squiz.cloud%2Fframework%2Ffunnelback%2Fpush-click-tracking-redirect%3FpushAsset%3D1916482&index_url=https%3A%2F%2Flgasa-web.squiz.cloud%2F%3Fa%3D1916482&auth=PpcRJ%2FNk1Bpame0ZpobrVw&profile=_default&rank=1&query=%21FunDoesNotExist"

print("--- Run 1 ---")
final_1 = check_redirect(url)

print("\n--- Run 2 (Same URL) ---")
final_2 = check_redirect(url)

if final_1 and final_2:
    if final_1 == final_2:
        print("\nStable redirects.")
    else:
        print("\nUNSTABLE redirects!")

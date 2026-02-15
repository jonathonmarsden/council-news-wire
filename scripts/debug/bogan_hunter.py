
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from curl_cffi import requests
from bs4 import BeautifulSoup
import time

def hunt_bogan():
    url = "https://www.bogan.nsw.gov.au/news"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.3 Safari/605.1.15"
    }
    
    for i in range(5):
        print(f"Attempt {i+1} for Bogan...")
        try:
            response = requests.get(url, impersonate="safari15_3", timeout=60, verify=False)
            if response.status_code == 200:
                print(f"Success! Length: {len(response.text)}")
                print("--- BODY SNIPPET ---")
                print(response.text[10000:12000])
                with open("bogan_debug.html", "w") as f:
                    f.write(response.text)
                print("Saved bogan_debug.html")

                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for potential article containers
                articles = soup.find_all('div', class_=True)
                print("Potential Classes in DIVs:")
                seen = set()
                for d in articles:
                    classes = " ".join(d.get('class'))
                    if "news" in classes or "post" in classes or "item" in classes:
                        if classes not in seen:
                            print(f"  - {classes}")
                            seen.add(classes)
                            
                # Look for article tags
                real_articles = soup.find_all('article')
                print(f"Found {len(real_articles)} <article> tags")
                for a in real_articles:
                    print(f"  Article classes: {a.get('class')}")

                # Look for headings in main content
                h2s = soup.find_all('h2')
                print(f"Found {len(h2s)} h2 tags. First 3:")
                for h in h2s[:3]:
                    print(f"  H2: {h.text.strip()} (Parent: {h.parent.name} class={h.parent.get('class')})")
                
                return
        except Exception as e:
            print(f"Failed: {e}")
        time.sleep(2)

if __name__ == "__main__":
    hunt_bogan()

import requests
from bs4 import BeautifulSoup
import sys

def analyze_url(name, url):
    print(f"\n--- Analyzing {name} ({url}) ---")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print("Failed to fetch.")
            return

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check for common Drupal lists
        views_rows = soup.select('.views-row')
        print(f"Found {len(views_rows)} .views-row elements")
        
        articles = soup.find_all('article')
        print(f"Found {len(articles)} <article> elements")
        
        # Analyze first article or row
        item = None
        if len(articles) > 0:
            item = articles[0]
            print("Sample <article> classes:", item.get('class'))
        elif len(views_rows) > 0:
            item = views_rows[0]
            print("Sample .views-row classes:", item.get('class'))
            
        if item:
            # Try to find date
            dates = item.find_all(['time', 'span', 'div'], class_=lambda x: x and 'date' in x.lower())
            for d in dates:
                print(f"  Possible Date: <{d.name} class='{d.get('class')}'>{d.get_text(strip=True)}")
                
            # Try to find title/link
            links = item.find_all('a')
            for l in links:
                if len(l.get_text(strip=True)) > 10:
                    print(f"  Possible Link: <a href='{l.get('href')}'>{l.get_text(strip=True)}</a>")

    except Exception as e:
        print(f"Error: {e}")

def check_west_daly():
    print("\n--- Checking West Daly Homepage ---")
    try:
        url = "https://www.westdaly.nt.gov.au/"
        response = requests.get(url, timeout=15)
        print(f"Homepage Status: {response.status_code}")
        if response.status_code == 200:
            print("Homepage is ALIVE. Checking /news...")
            news_url = "https://www.westdaly.nt.gov.au/news"
            resp2 = requests.get(news_url, timeout=15)
            print(f"News Status: {resp2.status_code}")
        else:
            print("Homepage is DOWN.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_url("Darwin", "https://www.darwin.nt.gov.au/news")
    analyze_url("Palmerston", "https://palmerston.nt.gov.au/news")
    check_west_daly()

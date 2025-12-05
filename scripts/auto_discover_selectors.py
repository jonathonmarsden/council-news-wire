import requests
from bs4 import BeautifulSoup
import json
import time

CONFIG_PATH = "states/wa/councils.json"
OUTPUT_PATH = "wa_selector_report.json"

# Load council configs
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

results = {}
for council in config["councils"]:
    url = council.get("news_url")
    council_id = council.get("id")
    council_name = council.get("name")
    if not url:
        continue
    print(f"Scraping {council_name} ({council_id}) ...")
    try:
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Try to auto-detect selectors
        containers = [tag.name for tag in soup.find_all(True) if tag.get("class") and "news" in " ".join(tag.get("class"))]
        articles = soup.find_all(["article", "div", "section", "li"])
        title = None
        date = None
        link = None
        for a in articles:
            if not title:
                title = a.find(["h1", "h2", "h3", "a", "span"], string=True)
            if not date:
                date = a.find(["time", "span", "div"], string=True)
            if not link:
                link = a.find("a", href=True)
            if title and date and link:
                break
        results[council_id] = {
            "container": containers[0] if containers else None,
            "title_selector": title.name if title else None,
            "date_selector": date.name if date else None,
            "link_selector": link.name if link else None,
            "sample_title": title.get_text(strip=True) if title else None,
            "sample_date": date.get_text(strip=True) if date else None,
            "sample_link": link["href"] if link else None,
        }
    except Exception as e:
        results[council_id] = {"error": str(e)}
    time.sleep(0.5)

with open(OUTPUT_PATH, "w") as f:
    json.dump(results, f, indent=2)

print(f"Selector discovery complete. Results saved to {OUTPUT_PATH}")

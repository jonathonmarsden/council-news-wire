import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Councils to update to RSS
RSS_UPDATES = {
    # NSW
    "Georges River Council": {
        "rss_url": "https://www.georgesriver.nsw.gov.au/Council/Media?rss=News",
        "state": "nsw"
    },
    "Bogan Shire": {
        "rss_url": "https://www.bogan.nsw.gov.au/news?format=feed&type=rss",
        "state": "nsw"
    },
    "Inverell Shire": {
        "rss_url": "https://inverell.nsw.gov.au/feed/",
        "state": "nsw"
    },
    "Upper Lachlan Shire": {
        "rss_url": "https://upperlachlan.nsw.gov.au/feed/",
        "state": "nsw"
    },
    # QLD
    "Bundaberg Council": {
        "rss_url": "https://www.brcnow.bundaberg.qld.gov.au/feed/",
        "state": "qld"
    },
    # WA
    "Shire of Cocos (Keeling) Islands": {
        "rss_url": "https://www.shire.cc/en/latest-news.feed?type=rss",
        "state": "wa"
    }
}

def update_councils():
    # Group by state usually, but simple iteration is fine for small batch
    
    for name, update_data in RSS_UPDATES.items():
        state = update_data['state']
        rss_url = update_data['rss_url']
        
        config_path = PROJECT_ROOT / 'states' / state / 'councils.json'
        
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                
            found = False
            for council in data['councils']:
                if council['name'] == name:
                    print(f"Updating {name} to RSS...")
                    # Set RSS URL
                    council['rss_url'] = rss_url
                    # Clear news_url to ensure factory picks RSS (or keep it for ref)
                    # ScraperFactory picks RSS if rss_url exists.
                    
                    found = True
                    break
                    
            if found:
                with open(config_path, 'w') as f:
                    json.dump(data, f, indent=4)
                print(f"Saved {state}/councils.json")
            else:
                print(f"Could not find {name} in {state}")
                
        except Exception as e:
            print(f"Error updating {name}: {e}")

if __name__ == "__main__":
    update_councils()

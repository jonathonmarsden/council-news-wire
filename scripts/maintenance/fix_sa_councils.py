import json
import os

# List of SA councils identified as broken (Batch 2 - The "Linked Void" Cluster)
target_councils = [
    "adelaide-hills",
    "alexandrina",
    "burnside",
    "ceduna",
    "tea-tree-gully",
    "unley",
    "west-torrens",
    "yankalilla",
    "yorke-peninsula",
    "port-adelaide-enfield"
]

def fix_sa_councils():
    file_path = 'states/sa/councils.json'
    
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    with open(file_path, 'r') as f:
        data = json.load(f)

    count = 0
    print(f"Scanning {len(data['councils'])} councils...")
    for council in data['councils']:
        if council['id'] in target_councils:
            print(f"Fixing {council['id']} - Adding impersonate: chrome124 and updating selectors")
            council['impersonate'] = "chrome124"
            council['scraper'] = "card_scraper"
            council['selectors'] = {
                "container": ".news-listing__item",
                "title": ".news-listing__item-title",
                "date": ".news-listing__item-date",
                "link": ".news-listing__item-link"
            }
            count += 1

    if count > 0:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\nSuccessfully updated {count} councils in {file_path}")
    else:
        print("\nNo councils needed updating.")

if __name__ == "__main__":
    fix_sa_councils()

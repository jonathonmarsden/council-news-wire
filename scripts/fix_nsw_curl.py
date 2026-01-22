import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NSW_CONFIG = PROJECT_ROOT / 'states' / 'nsw' / 'councils.json'

TARGETS = [
    "Northern Beaches Council",
    "Lithgow, City of",
    # Add hard blocks to try curl anyway, sometimes it helps if we tweak it later
    "Lake Macquarie, City of",
    "Tweed Shire",
    "Bellingen Shire",
    "Clarence Valley Council",
    "Murray River Council",
    "Murrumbidgee Council",
    "Narrandera Shire",
    "Snowy Valleys Council",
    "Uralla Shire"
]

def main():
    with open(NSW_CONFIG, 'r') as f:
        data = json.load(f)
        
    count = 0
    for council in data['councils']:
        if council['name'] in TARGETS:
            if not council.get('use_curl'):
                council['use_curl'] = True
                print(f"Enabled curl for {council['name']}")
                count += 1
            else:
                print(f"Curl already enabled for {council['name']}")
                
    if count > 0:
        with open(NSW_CONFIG, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Updated {count} councils.")
    else:
        print("No changes needed.")

if __name__ == "__main__":
    main()

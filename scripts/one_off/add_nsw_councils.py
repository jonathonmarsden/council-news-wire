import json
import re

EXISTING_FILE = "states/nsw/councils.json"

NEW_COUNCILS = [
    "Albury City Council", "Ballina Shire Council", "Balranald Shire Council", "Bellingen Shire Council",
    "Berrigan Shire Council", "Bland Shire Council", "Blayney Shire Council", "Bogan Shire Council",
    "Bourke Shire Council", "Brewarrina Shire Council", "Broken Hill City Council", "Byron Shire Council",
    "Cabonne Council", "Carrathool Shire Council", "Central Darling Shire Council", "Clarence Valley Council",
    "Cobar Shire Council", "Coolamon Shire Council", "Coonamble Shire Council", "Cootamundra-Gundagai Regional Council",
    "Cowra Council", "Dungog Shire Council", "Edward River Council", "Federation Council", "Forbes Shire Council",
    "Gilgandra Shire Council", "Glen Innes Severn Council", "Goulburn Mulwaree Council", "Greater Hume Council",
    "Griffith City Council", "Gunnedah Shire Council", "Gwydir Shire Council", "Hay Shire Council",
    "Hilltops Council", "Inverell Shire Council", "Junee Shire Council", "Kempsey Shire Council",
    "Kiama Municipal Council", "Kyogle Council", "Lachlan Shire Council", "Leeton Shire Council",
    "Lithgow City Council", "Liverpool Plains Shire Council", "Lockhart Shire Council", "Mid-Western Regional Council",
    "Moree Plains Shire Council", "Murray River Council", "Murrumbidgee Council", "Muswellbrook Shire Council",
    "Nambucca Valley Council", "Narrabri Shire Council", "Narrandera Shire Council", "Narromine Shire Council",
    "Oberon Council", "Parkes Shire Council", "Richmond Valley Council", "Shellharbour City Council",
    "Singleton Council", "Snowy Valleys Council", "Temora Shire Council", "Tenterfield Shire Council",
    "Upper Hunter Shire Council", "Upper Lachlan Shire Council", "Uralla Shire Council", "Walcha Council",
    "Walgett Shire Council", "Warren Shire Council", "Warrumbungle Shire Council", "Weddin Shire Council",
    "Wentworth Shire Council", "Wingecarribee Shire Council", "Wollondilly Shire Council", "Yass Valley Council"
]

def slugify(name):
    return name.lower().replace(" ", "-").replace("'", "")

def guess_url(name):
    slug = slugify(name)
    domain_slug = slug.replace("-council", "").replace("-shire", "").replace("-city", "").replace("-municipal", "").replace("-regional", "")
    if "upper-hunter" in slug: domain_slug = "upperhunter"
    return f"https://www.{domain_slug}.nsw.gov.au/News"

def main():
    with open(EXISTING_FILE, 'r') as f:
        data = json.load(f)
    
    existing_ids = {c['id'] for c in data['councils']}
    
    count = 0
    for name in NEW_COUNCILS:
        cid = slugify(name)
        if cid in existing_ids:
            print(f"Skipping {name} (exists)")
            continue
            
        entry = {
            "id": cid,
            "name": name,
            "news_url": guess_url(name),
            "scraper": "card_scraper",
            "enabled": True
        }
        data['councils'].append(entry)
        count += 1
        print(f"Added {name}")
        
    with open(EXISTING_FILE, 'w') as f:
        json.dump(data, f, indent=2)
        
    print(f"Added {count} new councils.")

if __name__ == "__main__":
    main()
